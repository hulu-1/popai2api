from pyvirtualdisplay import Display
import undetected_chromedriver as uc

def get_gtoken():
    # 启动Xvfb
    display = Display(visible=0, size=(1920, 1080), backend="xvfb")
    display.start()

    with open('./recaptcha__zh_cn.js', 'r', encoding='utf-8', errors='ignore') as f:
        str_js = f.read()
    
    options = uc.ChromeOptions()
    # 你可以添加其他Chrome选项
    options.add_argument('--disable-gpu')
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-dev-shm-usage')
    
    driver = uc.Chrome(options=options)
    driver.get('https://www.popai.pro/')
    gtoken = driver.execute_async_script(str_js)
    
    with open('gtoken.txt', 'a', encoding='utf-8', errors='ignore') as f:
        f.write(gtoken)
        f.write('\n')
    
    driver.quit()
    display.stop()  # 停止Xvfb
    return gtoken

def update_env_file(gtoken):
    env_file = '.env'
    key = 'G_TOKEN'
    updated = False

    with open(env_file, 'r') as f:
        lines = f.readlines()

    with open(env_file, 'w') as f:
        for line in lines:
            if line.startswith(f'{key}='):
                f.write(f'{key}={gtoken}\n')
                updated = True
            else:
                f.write(line)
        
        if not updated:
            f.write(f'{key}={gtoken}\n')

if __name__ == "__main__":
    gtoken = get_gtoken()
    update_env_file(gtoken)
