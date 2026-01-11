bind = '127.0.0.1:8000'

# Server 8 vCPU → ambil 12 worker (aman, stabil, tidak boros RAM)
workers = 6
worker_class = 'sync'

# sync worker tidak pakai threads
threads = 1

timeout = 120
keepalive = 5

# recycle worker untuk cegah memory leak
max_requests = 1000
max_requests_jitter = 200

accesslog = '/var/www/solar-panel-backend/logs/gunicorn.access'
errorlog = '/var/www/solar-panel-backend/logs/gunicorn.err'
loglevel = 'info'

user = 'www-data'
group = 'www-data'

# /dev/shm bagus untuk I/O cepat, aman dipakai
worker_tmp_dir = '/dev/shm'

wsgi_app = 'config.wsgi:application'

# preload_app = True bagus tapi hati-hati RAM
preload_app = True
