import os
import sys # noqa
import argparse
import random
import re
import time
import copy

from DrissionPage import ChromiumOptions
from DrissionPage import ChromiumPage
from DrissionPage._elements.none_element import NoneElement

from fun_utils import ding_msg
from fun_utils import get_date
from fun_utils import load_file
from fun_utils import save2file
from proxy_api import change_proxy

from conf import DEF_LOCAL_PORT
from conf import DEF_USE_HEADLESS
from conf import DEF_DEBUG
from conf import DEF_PATH_USER_DATA
from conf import DEF_PWD
from conf import DEF_MSG_FAIL
from conf import DEF_NUM_TRY
from conf import DEF_DING_TOKEN
from conf import DEF_PATH_BROWSER
from conf import DEF_AUTO_PROXY
from conf import DEF_PATH_DATA_PROXY
from conf import DEF_PATH_DATA_STATUS
from conf import DEF_HEADER_STATUS
from conf import logger

"""
2024.09.05
Base spin to earn points
"""


class BaseTask():
    def __init__(self) -> None:
        self.args = None
        self.page = None
        self.proxy_name = 'UNKNOWN(START)'
        self.proxy_info = 'USING'
        self.lst_proxy_cache = []
        self.lst_proxy_black = []
        self.s_today = get_date(is_utc=True)
        self.file_proxy = None

        self.n_points_spin = -1
        self.n_points = -1
        self.n_referrals = -1
        self.n_completed = -1

        # 账号执行情况
        self.dic_status = {}

    def set_args(self, args):
        self.args = args

        self.init_proxy()

        self.n_points_spin = -1
        self.n_points = -1
        self.n_referrals = -1
        self.n_completed = -1

    def __del__(self):
        self.proxy_save()
        self.status_save()
        logger.info(f'Exit {self.args.s_profile}')

    def status_load(self):
        self.file_status = f'{DEF_PATH_DATA_STATUS}/status_{self.s_today}.csv'
        self.dic_status = load_file(
            file_in=self.file_status,
            idx_key=0,
            header=DEF_HEADER_STATUS
        )

    def status_save(self):
        self.file_status = f'{DEF_PATH_DATA_STATUS}/status_{self.s_today}.csv'
        save2file(
            file_ot=self.file_status,
            dic_status=self.dic_status,
            idx_key=0,
            header=DEF_HEADER_STATUS
        )

    def init_proxy(self):
        if DEF_AUTO_PROXY:
            self.s_today = get_date(is_utc=True)
            self.file_proxy = f'{DEF_PATH_DATA_PROXY}/proxy_{self.s_today}.csv'
            self.lst_proxy_black = self.proxy_load()
            self.proxy_name = change_proxy(self.lst_proxy_black)
            logger.info(f'已开启自动更换 Proxy ，当前代理是 {self.proxy_name}')

    def close(self):
        # 在有头浏览器模式 Debug 时，不退出浏览器，用于调试
        if DEF_USE_HEADLESS is False and DEF_DEBUG:
            pass
        else:
            self.page.quit()

    def proxy_update(self, proxy_update_info):
        self.proxy_info = proxy_update_info
        self.proxy_save()
        self.lst_proxy_black = self.proxy_load()
        logger.info(f'准备更换 Proxy ，更换前的代理是 {self.proxy_name}')
        self.proxy_name = change_proxy(self.lst_proxy_black)
        logger.info(f'完成更换 Proxy ，更换后的代理是 {self.proxy_name}')
        self.proxy_info = 'USING'

    def proxy_load(self):
        lst_proxy_black = []

        if not DEF_AUTO_PROXY:
            return lst_proxy_black

        try:
            with open(self.file_proxy, 'r') as fp:
                # Skip the header line
                # next(fp)
                for line in fp:
                    if len(line.strip()) == 0:
                        continue
                    # 逗号分隔，Proxy Info 可能包含逗号
                    fields = line.strip().split(',')
                    proxy_name = fields[0]
                    proxy_info = ', '.join(fields[1:])
                    self.lst_proxy_cache.append([proxy_name, proxy_info])
                    if proxy_info in [DEF_MSG_FAIL]:
                        lst_proxy_black.append(proxy_name)
        except FileNotFoundError:
            pass
        except Exception as e:
            logger.info(f'[proxy_load] An error occurred: {str(e)}')

        return lst_proxy_black

    def proxy_save(self):
        if not DEF_AUTO_PROXY:
            return

        if not self.proxy_name:
            return

        if not self.file_proxy:
            self.s_today = get_date(is_utc=True)
            self.file_proxy = f'{DEF_PATH_DATA_PROXY}/proxy_{self.s_today}.csv'

        dir_file_out = os.path.dirname(self.file_proxy)
        if dir_file_out and (not os.path.exists(dir_file_out)):
            os.makedirs(dir_file_out)

        if not os.path.exists(self.file_proxy):
            with open(self.file_proxy, 'w') as fp:
                fp.write('Proxy Name,Proxy Info\n')

        b_new_proxy_name = True
        try:
            # 先读取原有内容以便更新
            proxies = []
            if os.path.exists(self.file_proxy):
                with open(self.file_proxy, 'r') as fp:
                    lines = fp.readlines()
                    for line in lines[1:]:  # 跳过头部
                        proxies.append(tuple(line.strip().split(',')))

            with open(self.file_proxy, 'w') as fp:
                fp.write('Proxy Name,Proxy Info\n')
                for fields in proxies:
                    proxy_name = fields[0]
                    proxy_info = ','.join(fields[1:])
                    if proxy_name == self.proxy_name:
                        proxy_info = self.proxy_info
                        b_new_proxy_name = False
                    fp.write(f'{proxy_name},{proxy_info}\n')  # noqa
                if b_new_proxy_name:
                    fp.write(f'{self.proxy_name},{self.proxy_info}\n')  # noqa
        except Exception as e:
            logger.info(f'[proxy_save] An error occurred: {str(e)}')

    def initChrome(self, s_profile):
        """
        s_profile: 浏览器数据用户目录名称
        """
        profile_path = s_profile

        co = ChromiumOptions()

        # 设置本地启动端口
        co.set_local_port(port=DEF_LOCAL_PORT)
        if len(DEF_PATH_BROWSER) > 0:
            co.set_paths(browser_path=DEF_PATH_BROWSER)
        # co.set_paths(browser_path='/Applications/Google Chrome.app/Contents/MacOS/Google Chrome') # noqa

        # 阻止“自动保存密码”的提示气泡
        co.set_pref('credentials_enable_service', False)

        # 阻止“要恢复页面吗？Chrome未正确关闭”的提示气泡
        co.set_argument('--hide-crash-restore-bubble')

        co.set_user_data_path(path=DEF_PATH_USER_DATA)
        co.set_user(user=profile_path)

        # https://drissionpage.cn/ChromiumPage/browser_opt
        co.headless(DEF_USE_HEADLESS)
        co.set_user_agent(user_agent='Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36') # noqa

        try:
            self.page = ChromiumPage(co)
        except Exception as e:
            logger.info(f'Error: {e}')
        finally:
            pass

    def open_coinbase(self):
        """
        https://chrome.google.com/webstore/detail/hnfanknocfeofbddgcijnmhnfnkdnaad
        chrome-extension://hnfanknocfeofbddgcijnmhnfnkdnaad/index.html?inPageRequest=false
        """
        EXTENSION_ID = 'hnfanknocfeofbddgcijnmhnfnkdnaad'
        logger.info('Open Coinbase to login ...')
        is_finish_load = self.page.get(f'chrome-extension://{EXTENSION_ID}/index.html') # noqa
        # is_finish_load = self.page.wait.load_start()
        if not is_finish_load:
            logger.info('打开 Coinbase 插件页安装插件')
            self.page.get('https://chrome.google.com/webstore/detail/hnfanknocfeofbddgcijnmhnfnkdnaad') # noqa
            time.sleep(1)
            sys.exit(-1)

        ele_input = self.page.ele('x://*[@id="cds-textinput-label-:r1:"]', timeout=2) # noqa
        if not isinstance(ele_input, NoneElement):
            logger.info('Coinbase Wallet 输入密码')
            ele_input.input(DEF_PWD)
            logger.info('Coinbase Unlock')
            self.page.ele('x://*[@id="app-main"]/div/div[1]/div/div/div[3]/div[2]/button').click(by_js=True) # noqa

        x_path = '//*[@id="page-container"]/div[1]/div[1]/div[1]/h1'
        balance = self.page.ele('x:{}'.format(x_path), timeout=2)
        if not isinstance(balance, NoneElement):
            logger.info('账户余额：{}'.format(balance.text))
        else:
            logger.info(
                'ERROR! Coinbase is invalid! profile:{}'
                .format(self.args.s_profile)
            )
            if DEF_USE_HEADLESS:
                self.page.quit()
            # sys.exit(-1)
        logger.info('Coinbase login success')

    def check_network(self):
        if len(self.page.html) == 0:
            s_proxy_pre = self.proxy_name
            logger.info('无法获取页面内容，请检查网络')
            if len(DEF_DING_TOKEN) > 0:
                d_cont = {
                    'title': '无法获取页面内容 [Base]',
                    'text': (
                        '- 页面为空\n'
                        '- 请检查网络\n'
                        '- profile: {s_profile}\n'
                        '- proxy_pre: {s_proxy_pre}\n'
                        '- proxy_now: {s_proxy_now}\n'
                        .format(
                            s_profile=self.args.s_profile,
                            s_proxy_pre=s_proxy_pre,
                            s_proxy_now=self.proxy_name
                        )
                    )
                }
                ding_msg(d_cont, DEF_DING_TOKEN, msgtype="markdown")
            self.page.quit()
            if DEF_AUTO_PROXY:
                self.proxy_update(DEF_MSG_FAIL)

        try:
            # 检查网络连接是否正常
            x_path = '//*[@id="error-information-popup-content"]/div[2]'
            s_info = self.page.ele('x:{}'.format(x_path), timeout=2).text
            if 'ERR_CONNECTION_RESET' == s_info:
                logger.info('无法访问此网站')
                if len(DEF_DING_TOKEN) > 0:
                    d_cont = {
                        'title': 'Network Error',
                        'text': (
                            '- 无法访问此网站\n'
                            '- 连接已重置\n'
                            '- profile: {s_profile}\n'
                            '- proxy: {s_proxy}\n'
                            .format(
                                s_profile=self.args.s_profile,
                                s_proxy=self.proxy_name
                            )
                        )
                    }
                    ding_msg(d_cont, DEF_DING_TOKEN, msgtype="markdown")
                self.page.quit()
                if DEF_AUTO_PROXY:
                    self.proxy_update(DEF_MSG_FAIL)
        except: # noqa
            pass

    def fun_spin(self):
        """
        Return:
            True: Already Spun
            False: To Spun
        """
        for i in range(DEF_NUM_TRY):
            logger.info('spin try_i={}'.format(i+1))

            # 页面左上角按钮
            # x_path = '//*[@id="__next"]/div/div[1]/div[1]/div/nav/div[1]/div/button' # noqa
            # button = self.page.ele('x:{}'.format(x_path))
            # button.click()

            logger.info('CLICK Today Button ...')
            x_path = '//*[@id="tab--today"]'
            button = self.page.ele('x:{}'.format(x_path))
            if isinstance(button, NoneElement):
                logger.info('没有 Today 标签，从头重试 ...')
                continue
            else:
                button.click()

            logger.info('Show POINTS/REFERRALS/COMPLETED ...')
            s_path = '.:cds-flex-f1g67tkn cds-row-r1tfxker cds-space-between-s1vbz1 cds-2-' # noqa
            self.page.wait.eles_loaded(f'{s_path}')
            self.page.actions.move_to(f'{s_path}')
            ele_info = self.page.eles(f'{s_path}', timeout=2)
            if isinstance(ele_info, NoneElement):
                logger.info('没有 POINTS/REFERRALS/COMPLETED，从头重试 ...')
                continue
            else:
                s_info = ele_info[-1].text.replace(',', '')
                numbers = re.findall(r'\d{1,},?\d*', s_info)
                if len(numbers) == 3:
                    n_points = numbers[0]
                    n_referrals = numbers[1]
                    n_completed = numbers[2]
                    if self.args.s_profile in self.dic_status:
                        self.dic_status[self.args.s_profile][2] = n_points
                        self.dic_status[self.args.s_profile][3] = n_referrals
                        self.dic_status[self.args.s_profile][4] = n_completed
                    else:
                        self.dic_status[self.args.s_profile] = [
                            self.args.s_profile,
                            -1, n_points, n_referrals, n_completed
                        ]

            logger.info('CLICK BUTTON: SPIN TO EARN POINTS ...')
            s_path = '@data-testid=spinwheelButton'
            self.page.wait.eles_loaded(f'{s_path}')
            self.page.actions.move_to(f'{s_path}')
            button = self.page.ele(f'{s_path}', timeout=2)
            if isinstance(button, NoneElement):
                logger.info('没有 SPIN TO EARN POINTS 按钮，从头重试 ...')
                continue
            else:
                button.click(by_js=True)

            # 等页面都加载完，网速慢的时候，按钮状态未更新
            self.page.wait.load_start()

            logger.info('等待转盘加载 ...')
            if self.page.wait.eles_loaded('.sc-gsTCUz bhdLno'):
                self.page.actions.move_to('.sc-gsTCUz bhdLno')

            logger.info('等待加载 Spin the wheel 按钮  ...')

            # 如果已经抽过
            s_path = 'You already spun the wheel today' # noqa
            if self.page.wait.eles_loaded(s_path, timeout=3):
                self.page.actions.move_to(s_path)
                logger.info('You already spun the wheel today  ...')
                return True
            else:
                pass

            s_path = '@@data-testid=spinWheelButton@@text()=Spin the wheel' # noqa
            if self.page.wait.eles_loaded(s_path):
                self.page.actions.move_to(s_path)
            else:
                logger.info('没有 Spin the wheel 按钮，从头重试 ...')
                # continue

            button = self.page.ele(s_path, timeout=2)
            if isinstance(button, NoneElement):
                logger.info('没有按钮，从头重试 ...')
                continue
            if button.text == 'Explore experiences':
                logger.info('Explore experiences ...')
                x_path = '//*[@id="modalsContainer"]/div/div/div[2]/div/div[2]/div/div[2]/p[1]' # noqa
                # You already spun the wheel today!
                s_info = self.page.ele('x:{}'.format(x_path), timeout=2).text
                logger.info(s_info)
                return True

            if button.text == 'Spin the wheel':
                button.click(by_js=True)

            def update_spin_points(s_info):
                numbers = re.findall(r'\d+', s_info.replace(',', ''))

                if self.args.s_profile in self.dic_status:
                    self.dic_status[self.args.s_profile][1] = numbers[0]
                else:
                    self.dic_status[self.args.s_profile] = [
                        self.args.s_profile,
                        -1, -1, -1, -1
                    ]

            # Hooray, you earned 300 points!
            for j in range(1, 10):
                try:
                    s_toast = self.page.ele('#toastsContainer', timeout=1).text
                    if len(s_toast) > 0:
                        logger.info(f'Toast: {s_toast}')
                        if s_toast.startswith('You earned '):
                            update_spin_points(s_toast)
                            return True
                except: # noqa
                    pass
                x_path = '//*[@id="modalsContainer"]/div/div/div[2]/div/div[2]/div/div[2]/p[1]' # noqa
                ele_info = self.page.ele('x:{}'.format(x_path), timeout=2)
                if isinstance(ele_info, NoneElement):
                    # logger.info('没有按钮，重试 ...')
                    pass
                else:
                    logger.info(ele_info.text)
                    if ele_info.text.startswith('Hooray, you earned'):
                        update_spin_points(ele_info.text)
                        return True
                    else:
                        pass
                logger.info(f'sleep {j * 2} 秒，等待...')
                time.sleep(j * 2)

        return False

    def base_login(self):
        # Connect
        x_path = '//*[@id="__next"]/div/div[1]/div[1]/nav/div/div[2]/div/div/button[2]' # noqa
        button = self.page.ele('x:{}'.format(x_path), timeout=2)
        if isinstance(button, NoneElement):
            logger.info('没有获取到页面右上角按钮')
            return

        logger.info('Connect Wallet ...')
        if button.text == 'Connect':
            logger.info('点击 Connect 按钮 ...')
            button.click()

            # 选择登录的钱包
            x_path = '//*[@id="__next"]/div/div[1]/div[2]/div/div/div/ul/li[1]/button' # noqa
            self.page.wait.eles_loaded('x:{}'.format(x_path))
            self.page.actions.move_to('x:{}'.format(x_path))
            button = self.page.ele('x:{}'.format(x_path))
            logger.info('正在点击 WALLET 连接 钱包 ...')
            button.click(by_js=True)

            # Select your wallet type
            logger.info('Select your wallet type')
            x_path = '//*[@id="__next"]/div/div[1]/div[2]/div/div/div/div[2]/div[2]/button' # noqa
            button = self.page.ele('x:{}'.format(x_path))
            logger.info('Sign in your browser extension ...')
            button.click(by_js=True)

            # Coinbase Wallet 连接
            logger.info('Coinbase Wallet 连接到网站')
            # 需要等待弹窗加载完成
            self.page.wait.load_start()
            if DEF_DEBUG:
                print(self.page.tab_ids)
            if len(self.page.tab_ids) == 2:
                try:
                    tab_id = self.page.latest_tab
                    tab_new = self.page.get_tab(tab_id)
                    x_path = '//*[@id="app-main"]/div/div/div/div/div/div[3]/div/ul/li[2]/button' # noqa
                    button = tab_new.ele('x:{}'.format(x_path), timeout=2)
                    logger.info('{}'.format(button.text))
                    button.click()
                except: # noqa
                    pass

            # Select a wallet
            x_path = '//*[@id="modalsContainer"]/div/div/div[2]/div/div[2]/div/button' # noqa
            button = self.page.ele('x:{}'.format(x_path), timeout=2)
            if isinstance(button, NoneElement):
                logger.info('没有 Confirm Button')
            else:
                logger.info('{}'.format(button.text))
                button.click()

    def base_init(self):
        """
        登录及校验是否登录成功
        """
        self.page.get('https://wallet.coinbase.com/ocs/today')

        for i in range(1, 10):
            logger.info('Page Login try_i={}'.format(i+1))
            self.base_login()

            logger.info('检查是否登录成功 ...')
            time.sleep(1)

            # 这是已登录时的 xpath
            x_path = '//*[@id="__next"]/div/div[1]/div[2]/nav/div/div[2]/div/div[1]/div/div/button' # noqa
            self.page.wait.eles_loaded('x:{}'.format(x_path))
            button = self.page.ele('x:{}'.format(x_path), timeout=2)
            if isinstance(button, NoneElement):
                # 没有获取到已登录的 xpath
                pass
            elif button.text == '\ued0a':
                logger.info('页面已成功登录')
                break
            else:
                pass


def main(args):
    if args.sleep_sec_at_start > 0:
        logger.info(f'Sleep {args.sleep_sec_at_start} seconds at start !!!') # noqa
        time.sleep(args.sleep_sec_at_start)

    if len(args.profile) > 0:
        items = args.profile.split(',')
    else:
        # 生成 p001 到 p020 的列表
        items = [f'p{i:03d}' for i in range(args.purse_start_id, args.purse_end_id+1)] # noqa
        # items = ['p012']
        # items = ['p012', 'p015']

    profiles = copy.deepcopy(items)

    # 每次随机取一个出来，并从原列表中删除，直到原列表为空
    total = len(items)
    n = 0
    instBaseTask = BaseTask()

    while items:
        n += 1
        logger.info('#'*40)
        s_profile = random.choice(items)
        logger.info(f'progress:{n}/{total} [{s_profile}]') # noqa
        items.remove(s_profile)

        args.s_profile = s_profile

        # 切换 IP 后，可能出现异常(与页面的连接已断开)，增加重试
        max_try_except = 3
        for j in range(1, max_try_except+1):
            try:
                is_spin = False
                if j > 1:
                    logger.info(f'异常重试，当前是第{j}次执行，最多尝试{max_try_except}次 [{s_profile}]') # noqa
                instBaseTask.set_args(args)
                instBaseTask.status_load()

                if s_profile in instBaseTask.dic_status:
                    lst_status = instBaseTask.dic_status[s_profile]
                else:
                    lst_status = None

                if lst_status and int(lst_status[1]) > 0:
                    logger.info(f'[{s_profile}] Spin 已完成')
                else:
                    instBaseTask.initChrome(s_profile)
                    instBaseTask.open_coinbase()
                    instBaseTask.base_init()
                    is_spin = instBaseTask.fun_spin()
                    instBaseTask.close()
                    instBaseTask.status_save()

                if is_spin:
                    break
            except Exception as e:
                logger.info(f'[{s_profile}] An error occurred: {str(e)}')
                if j < max_try_except:
                    time.sleep(5)

        logger.info('Finish')

        if len(items) > 0:
            sleep_time = random.randint(args.sleep_sec_min, args.sleep_sec_max)
            if sleep_time > 60:
                logger.info('sleep {} minutes ...'.format(int(sleep_time/60)))
            else:
                logger.info('sleep {} seconds ...'.format(int(sleep_time)))
            time.sleep(sleep_time)

    if len(DEF_DING_TOKEN) > 0:
        s_info = ''
        for s_profile in profiles:
            if s_profile in instBaseTask.dic_status:
                lst_status = instBaseTask.dic_status[s_profile]
            else:
                lst_status = [s_profile, -1, -1, -1, -1]
            s_info += '- {} {}/{} {} {}\n'.format(
                s_profile,
                lst_status[1],
                lst_status[2],
                lst_status[3],
                lst_status[4]
            )
        d_cont = {
            'title': 'Base Spin Finished',
            'text': (
                '- points,referrals,completed\n'
                '{}\n'
                .format(s_info)
            )
        }
        ding_msg(d_cont, DEF_DING_TOKEN, msgtype="markdown")


if __name__ == '__main__':
    """
    生成 p001 到 p999 的列表
    例如 ['p001', 'p002', 'p003', ...]
    每次随机取一个出来，并从原列表中删除，直到原列表为空
    """
    parser = argparse.ArgumentParser()
    parser.add_argument(
        '--purse_start_id', required=False, default=1, type=int,
        help='[默认为 1] 首个账号 ID'
    )
    parser.add_argument(
        '--purse_end_id', required=False, default=20, type=int,
        help='[默认为 20] 最后一个账号的 ID'
    )
    parser.add_argument(
        '--sleep_sec_min', required=False, default=3, type=int,
        help='[默认为 3] 每个账号执行完 sleep 的最小时长(单位是秒)'
    )
    parser.add_argument(
        '--sleep_sec_max', required=False, default=10, type=int,
        help='[默认为 10] 每个账号执行完 sleep 的最大时长(单位是秒)'
    )
    parser.add_argument(
        '--sleep_sec_at_start', required=False, default=0, type=int,
        help='[默认为 0] 在启动后先 sleep 的时长(单位是秒)'
    )
    parser.add_argument(
        '--profile', required=False, default='',
        help='按指定的 profile 执行，多个用英文逗号分隔'
    )
    args = parser.parse_args()
    main(args)
