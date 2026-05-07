import subprocess, time, sys, os

script = 'bot.py'
python = sys.executable

print('KOREA EXP BOT KEEP_ALIVE - 24/7')
print('Starting at', time.strftime('%Y-%m-%d %H:%M:%S'))

while True:
    try:
        env = os.environ.copy()
        env['PYTHONIOENCODING'] = 'utf-8'
        
        proc = subprocess.Popen([python, script], stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=env)
        print('Bot started PID:', proc.pid)
        
        while True:
            ret = proc.poll()
            if ret is not None:
                print('Bot stopped (code', ret, '), restarting...')
                break
            time.sleep(10)
        
        time.sleep(5)
        
    except KeyboardInterrupt:
        print('Stopped by user')
        break
    except Exception as e:
        print('Error:', e)
        time.sleep(5)