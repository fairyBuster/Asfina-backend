bind = '127.0.0.1:8000'

# Server 5 vCPU -> (2 x 5) + 1 = 11 workers
workers = 11
worker_class = 'gthread'

# gthread worker pakai threads (Safe: 11 workers * 10 threads = 110 concurrent)
threads = 10

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
