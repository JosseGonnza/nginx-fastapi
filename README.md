<img width="100%" src="https://capsule-render.vercel.app/api?type=waving&color=0:009639,100:2496ED&animation=fadeIn&height=120&section=header"/>

# nginx-fastapi

Ejercicio del Bloque 2 de **0614 · Despliegue de aplicaciones web** (2º DAW).

Nginx atiende todas las peticiones en un único puerto y hace dos cosas distintas según la ruta:

| Ruta | Quién responde | Cómo |
|---|---|---|
| `/` | **Nginx** | Lee `index.html` del disco y lo devuelve tal cual (`text/html`). |
| `/users` | **FastAPI** | Nginx reenvía la petición a uvicorn y devuelve su respuesta (`application/json`). |

El objetivo es ver la diferencia entre **servir un archivo** y **reenviar una petición** a una aplicación.

## Cómo ejecutarlo

Requiere Docker con Compose.

```bash
docker compose up -d --build
```

| URL | Resultado |
|---|---|
| <http://localhost:8080> | Página estática servida por Nginx |
| <http://localhost:8080/users> | JSON de FastAPI, a través de Nginx |

Para pararlo:

```bash
docker compose down
```

## Estructura

```
nginx-fastapi/
├── docker-compose.yml     Los dos servicios y cómo se conectan
├── nginx/
│   ├── default.conf       Sitio de Nginx: archivo estático en / y proxy en /users
│   └── html/index.html    Página estática
├── api/
│   ├── Dockerfile         Imagen de la API: Python 3.14 + uvicorn
│   ├── main.py            FastAPI con el endpoint de prueba GET /users
│   └── requirements.txt
├── docs/access.log        Copia del access.log de Nginx para la entrega
└── logs/                  access.log y error.log en vivo (no se versiona)
```

## Arquitectura

```
                    ┌──────────────── red interna de Docker ────────────────┐
Navegador ──:8080──▶│ nginx :80 ──┬── /       → /usr/share/nginx/html/index.html │
                    │             └── /users  → proxy_pass → api :8000 (uvicorn) │
                    └────────────────────────────────────────────────────────┘
```

- Solo `nginx` publica un puerto (`8080:80`). `api` no tiene `ports`, así que desde fuera no se puede llamar directamente: todas las peticiones pasan por Nginx.
- Dentro de la red que crea Compose, cada servicio es accesible por su nombre. Por eso Nginx encuentra la API en `http://api:8000`.

```
$ docker compose ps
SERVICE   IMAGE               STATUS          PORTS
api       nginx-fastapi-api   Up 39 minutes
nginx     nginx:1.30.6        Up 22 minutes   0.0.0.0:8080->80/tcp, [::]:8080->80/tcp
```

## Configuración de Nginx

[`nginx/default.conf`](nginx/default.conf):

```nginx
server {
    listen 80;
    server_name localhost;

    root /usr/share/nginx/html;
    index index.html;

    location / {
        try_files $uri $uri/ =404;
    }

    location /users {
        proxy_pass http://api:8000;
        proxy_set_header Host $http_host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

| Directiva | Para qué |
|---|---|
| `listen 80` | Puerto dentro del contenedor. Docker lo publica en el 8080 de la máquina. |
| `root` + `index` | Carpeta de los archivos estáticos y archivo que se devuelve al pedir `/`. |
| `try_files $uri $uri/ =404` | Busca el archivo, después la carpeta, y si no encuentra ninguno responde `404`. **Servir un archivo.** |
| `location /users` | Atiende las URLs que empiezan por `/users`. Nginx elige el prefijo más largo que coincide, así que gana a `location /`. |
| `proxy_pass http://api:8000` | Reenvía la petición al contenedor `api`. Como no hay ruta después del puerto, la URL llega a FastAPI sin cambios. **Reenviar una petición.** |
| `proxy_set_header Host $http_host` | Pasa el `Host` original **con el puerto**. Con `$host` el puerto se pierde, y la redirección `307` de FastAPI de `/users/` a `/users` acababa en `http://localhost/users`, sin el `:8080`. |
| `X-Real-IP` · `X-Forwarded-For` | Sin ellas, FastAPI solo vería la IP de Nginx y no la del cliente real. |
| `X-Forwarded-Proto` | Indica si el cliente llegó por HTTP o HTTPS. |

## La API

[`api/main.py`](api/main.py) es un endpoint de prueba con una lista fija:

```python
@app.get("/users")
async def listar_users():
    return [{"id": 1, "nombre": "Ana"}, {"id": 2, "nombre": "Luis"}, {"id": 3, "nombre": "Marta"}]
```

El [`Dockerfile`](api/Dockerfile) arranca uvicorn con `--host 0.0.0.0`. Dentro de un contenedor, `127.0.0.1` solo acepta conexiones del propio contenedor, y Nginx está en otro.

## Comprobación

Las dos rutas responden por el mismo puerto, pero con orígenes distintos. Se ve en el `Content-Type`:

```
$ curl -i http://localhost:8080/
HTTP/1.1 200 OK
Server: nginx/1.30.6
Content-Type: text/html

<!DOCTYPE html> ...

$ curl -i http://localhost:8080/users
HTTP/1.1 200 OK
Server: nginx/1.30.6
Content-Type: application/json

[{"id":1,"nombre":"Ana"},{"id":2,"nombre":"Luis"},{"id":3,"nombre":"Marta"}]
```

| Petición | Código | Quién la resuelve |
|---|---|---|
| `GET /` | `200` | Nginx (archivo) |
| `GET /users` | `200` | FastAPI (vía proxy) |
| `GET /users/` | `307` → `/users` | FastAPI redirige y Nginx mantiene el puerto |
| `GET /noexiste` | `404` | Nginx (no existe el archivo) |

`curl -I` (petición `HEAD`) devuelve `405` en `/users`, porque FastAPI solo acepta en esa ruta el método declarado, `GET`. Para ver las cabeceras de las dos rutas hay que usar `curl -i`.

## access.log

El `access.log` de la imagen oficial de Nginx es un enlace a `/dev/stdout`. En `docker-compose.yml` se monta `./logs` sobre `/var/log/nginx`, y así Nginx escribe archivos reales en la carpeta `logs/` del proyecto:

```bash
tail -f logs/access.log
```

Copia en [`docs/access.log`](docs/access.log):

```
172.21.0.1 - - [28/Oct/2026:14:54:14 +0000] "GET /users HTTP/1.1" 200 76 "-" "curl/8.22.0" "-"
172.21.0.1 - - [28/Oct/2026:14:54:14 +0000] "GET /users/ HTTP/1.1" 307 0 "-" "curl/8.22.0" "-"
172.21.0.1 - - [28/Oct/2026:14:54:14 +0000] "GET /noexiste HTTP/1.1" 404 153 "-" "curl/8.22.0" "-"
172.21.0.1 - - [28/Oct/2026:14:54:19 +0000] "GET / HTTP/1.1" 200 422 "-" "curl/8.22.0" "-"
```

Formato `main` de Nginx: IP del cliente · fecha · petición · código · bytes enviados · *referer* · *user-agent* · `X-Forwarded-For`.

Comparado con el log de uvicorn (`docker compose logs api`), se ve el reparto de trabajo:

```
INFO:     172.21.0.2:42690 - "GET /users HTTP/1.1" 200 OK
INFO:     172.21.0.2:42694 - "GET /users/ HTTP/1.1" 307 Temporary Redirect
```

- **Nginx registra todas las peticiones**: `/`, `/users` y el `404`.
- **uvicorn solo ve las de `/users`**: el resto no le llega.
- **Cambia la IP**: Nginx ve al cliente (`172.21.0.1`, la puerta de enlace de la red de Docker) y uvicorn ve a Nginx (`172.21.0.2`).

### Notas

- `docker compose logs nginx` ya no muestra los accesos, porque ahora van al archivo.
- Los archivos de `logs/` los crea Nginx como `root`. Si la carpeta `logs/` no existe antes de arrancar, también la crea Docker como `root`, y para borrarla hará falta `sudo`. Para evitarlo, basta con crearla antes con `mkdir logs`.
- Si se edita `default.conf` y el cambio no se aplica, hay que recrear el contenedor con `docker compose up -d --force-recreate nginx`. Al montar un solo archivo, algunos editores lo guardan creando un archivo nuevo, y el contenedor sigue viendo el anterior. Para comprobar la configuración antes: `docker compose exec nginx nginx -t`.

<img width="100%" src="https://capsule-render.vercel.app/api?type=waving&color=0:2496ED,100:009639&height=80&section=footer"/>
