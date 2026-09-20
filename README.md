# Kick Clipper — versión GitHub (gratis, sin servidor propio)

Vigila canales de Kick, puntúa cada clip por potencial de tendencia y descarga
los mejores en máxima calidad. Todo dentro de GitHub, sin pagar nada.

- **GitHub Actions** hace de servidor: un cron se despierta cada 20 minutos, revisa los canales, puntúa y descarga.
- **Releases** hace de disco duro: los mp4 se suben ahí y los bajas con un clic.
- **GitHub Pages** hace de tablero: una página estática que lee `docs/data/clips.json`.

Tu PC puede estar apagada. Nada corre en local.

---

## Montarlo (10 minutos)

**1. Crea el repo.** Sube estos archivos a un repo nuevo. Hazlo **público**: los
minutos de Actions son ilimitados en repos públicos y limitados en privados. Si
lo pones privado, tienes 2.000 minutos al mes, que dan para unas 200 pasadas.

**2. Dale permiso de escritura al workflow.**
`Settings → Actions → General → Workflow permissions → Read and write permissions`.
Sin esto no puede guardar el JSON ni crear el release.

**3. Enciende Pages.**
`Settings → Pages → Source: Deploy from a branch → rama main, carpeta /docs`.
En un minuto tienes el tablero en `https://TU_USUARIO.github.io/TU_REPO/`.

**4. Pon tus canales** en `canales.txt`, uno por línea.

**5. Lánzalo a mano la primera vez.**
`Actions → Clipper → Run workflow`. A partir de ahí va solo cada 20 minutos.

---

## Pedir descargas desde el tablero

Los botones "Descargar" de la página disparan el workflow por la API de GitHub,
así que necesitan un token:

1. [Fine-grained token](https://github.com/settings/tokens?type=beta) → *Only select repositories* → tu repo.
2. Permisos: **Actions: Read and write** y **Contents: Read-only**.
3. Pégalo en la barra lateral del tablero. Se guarda solo en tu navegador.

Sin token la página sigue funcionando de sobra: ves el ranking y bajas lo que el
cron ya descargó solo. El token es solo para pedir extras a mano.

---

## Ajustes

Están arriba del todo de `.github/workflows/clipper.yml`, en `env:`

| Variable | Qué hace |
|---|---|
| `AUTO_DOWNLOAD_SCORE` | Descarga sola lo que pase de este puntaje. 72 es un buen punto de partida |
| `MAX_DOWNLOADS_PER_RUN` | Tope por pasada. 4 evita que una tanda se coma media hora de runner |
| `CLIPS_PER_SCAN` | Clips que pide por canal. Bájalo si Kick te empieza a cortar |
| `MAKE_VERTICAL` | Genera además el mp4 1080×1920 con fondo borroso para Shorts/TikTok |

Y el cron, en la línea `- cron: "*/20 * * * *"`. GitHub no admite menos de 5
minutos y en la práctica se retrasa entre 5 y 15, así que no ganas nada bajando
mucho de 15.

---

## Las tres pegas de hacerlo en GitHub (léelas antes de montarlo)

**1. Cloudflare y las IPs de los runners.** Kick está detrás de Cloudflare y los
runners de GitHub salen por IPs de datacenter, que es justo lo que Cloudflare
mira con lupa. Con `curl_cffi` imitando la huella TLS de Chrome suele pasar, pero
puede fallar a rachas. Si ves muchos avisos de "bloqueado por Cloudflare", añade
el secreto `KICK_PROXY` (`Settings → Secrets → Actions`) con un proxy
residencial en formato `http://usuario:clave@host:puerto` y todo el tráfico sale
por ahí. Es la única parte de esta arquitectura que puede darte guerra de verdad.

**2. Los crons se apagan solos.** GitHub desactiva los workflows programados tras
60 días sin actividad del repo y te avisa por correo. Entra cada tanto y
reactívalo, o haz un commit de vez en cuando.

**3. No es instantáneo.** Entre que pides una descarga y aparece el archivo pasan
2-4 minutos. Si quieres inmediatez, corre la versión local que tienes en el otro
proyecto: es la misma lógica de puntaje, pero con un servidor de verdad.

Si esto se te queda corto, el siguiente escalón gratis de verdad es una máquina
**Oracle Cloud Always Free** (ARM, 24 GB de RAM, para siempre): IP normal, sin
límite de minutos y le enchufas la versión local tal cual.

---

## Cómo se decide qué clip es bueno

No gana el que más vistas tiene, gana el que **se sale de la curva de su propio
canal**. Cinco señales, y el medidor de colores de cada fila te dice de dónde
sale cada punto:

| Señal | Peso | Qué mide |
|---|---|---|
| Velocidad | 34 | Vistas por hora. Desde la segunda revisión usa el crecimiento real entre pasadas, que es mucho más fiable |
| Anomalía | 28 | Cuántas veces supera la velocidad mediana de ese canal. 8× es el techo |
| Enganche | 14 | Likes sobre vistas |
| Duración | 14 | Curva centrada en 25-45s. Pasados 2 minutos hay castigo extra |
| Frescura | 10 | Un clip de hoy vale más que uno de hace un mes |

Toca `PESOS` en `app/scoring.py` si tu criterio es otro.

---

## Estructura

```
canales.txt                  tu lista de canales
.github/workflows/clipper.yml  el cron y los pasos
app/kick.py                  habla con la API de Kick (con soporte de proxy)
app/scoring.py               el puntaje 0-100
scripts/escanear.py          revisa canales y actualiza el JSON
scripts/descargar.py         yt-dlp + ffmpeg + subida al release
scripts/marcar.py            descartar / reintentar
docs/index.html              el tablero
docs/data/clips.json         el estado, versionado en el repo
```

## Un apunte

Los clips son de los streamers que los crearon. Antes de subirlos a tus canales
mira la política de cada uno: muchos lo permiten y agradecen el crédito, otros
no. Poner el nombre del canal en el título y en pantalla te ahorra strikes.
