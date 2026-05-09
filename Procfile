web: gunicorn -w 1 -b 0.0.0.0:$PORT bot:app
worker: APP_ROLE=worker python bot.py
