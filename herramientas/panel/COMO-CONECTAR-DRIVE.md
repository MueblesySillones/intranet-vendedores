# Conectar el panel con Drive

El panel necesita leer planillas y documentos que están en Drive. Como esos
archivos tienen datos de clientes, **no se comparten por link público**: el
panel entra con una cuenta propia y los lee en privado, desde esta computadora.

La idea, en una frase:

> Google te da una **dirección de mail** para el panel. Vos le compartís los
> archivos a esa dirección, igual que se los compartirías a un compañero.

La configuración de abajo se hace **una sola vez**. Después, cada planilla
nueva es solo compartirla.

---

## Primera parte: crear la cuenta del panel (una sola vez)

Todo esto pasa en la consola de Google Cloud. Suena más grande de lo que es:
son cinco pantallas y no hay que pagar nada.

### 1. Crear un proyecto

Entrá a **console.cloud.google.com** con la cuenta de Google de la empresa
(la misma donde viven las planillas, o cualquiera — no importa cuál).

Arriba, al lado del logo, hay un selector de proyecto. Abrilo y elegí
**Proyecto nuevo**. Ponele un nombre que después reconozcas, por ejemplo
`Panel Muebles y Sillones`. Dale a **Crear** y esperá unos segundos.

> Si es la primera vez que entrás, Google va a pedirte que aceptes los términos.
> No pide tarjeta.

### 2. Prender las dos APIs

Google mantiene todo apagado hasta que decís qué vas a usar.

En el buscador de arriba escribí **Google Sheets API** y entrá al resultado.
Apretá **Habilitar**.

Repetí lo mismo con estas dos:

- **Google Docs API** — para leer documentos.
- **Google Drive API** — para que el panel pueda mostrarte la **lista** de los
  archivos que le compartiste, y no tengas que andar pegando links.

> Si te olvidás de este paso, el panel va a decir *"Falta activar la API de
> Google en el proyecto"*. Volvé acá.

### 3. Crear la cuenta de servicio

En el buscador de arriba escribí **Cuentas de servicio** y entrá.

Apretá **Crear cuenta de servicio**:

- **Nombre**: `panel-mys` (o el que quieras).
- Apretá **Crear y continuar**.
- Cuando te ofrezca **conceder acceso a un rol**: no elijas ninguno.
  Apretá **Continuar** y después **Listo**.

> No es un olvido: los roles sirven para los recursos de Google Cloud, y el
> panel no usa ninguno. El permiso para leer una planilla no sale de acá —
> sale de compartirle el archivo, en la segunda parte.

Ahora vas a ver la cuenta en la lista, con una dirección larga que termina en
`.iam.gserviceaccount.com`. **Esa es la dirección del panel.**

### 4. Bajar el archivo de la cuenta

Hacé clic en la cuenta que acabás de crear. Andá a la pestaña **Claves** y
elegí **Agregar clave → Crear clave nueva → JSON → Crear**.

Se te va a bajar un archivo `.json`.

> ⚠️ **Ese archivo es una llave, no un dato.** El que lo tenga puede leer todo
> lo que se le haya compartido a esa cuenta. No lo mandes por mail ni por
> WhatsApp. Una vez que lo cargues en el panel (paso 5), podés borrarlo de la
> carpeta de Descargas: el panel se queda con su propia copia guardada.

### 5. Cargarlo en el panel

Abrí el panel → **Datos** → **Agregar un reporte** → pestaña
**Una planilla o documento de Google**.

Arrastrá el archivo `.json` a la caja, o apretá **Elegir el archivo…** y
buscalo en Descargas.

Listo. El panel te va a mostrar la dirección de la cuenta, con un botón de
**Copiar** al lado.

---

## Segunda parte: compartir cada archivo

Esto es lo único que hay que hacer de acá en adelante, y es lo mismo que hacés
todos los días con cualquier planilla.

1. En el panel, apretá **Copiar** al lado de la dirección.
2. Abrí la planilla (o el documento) en Drive.
3. Apretá **Compartir**, arriba a la derecha.
4. Pegá la dirección.
5. Dejala en **Lector**. No hace falta que pueda editar.
6. **Destildá "Notificar a las personas".**
7. Apretá **Compartir**.

> El punto 6 importa: no es una casilla de mail de verdad, así que la
> notificación rebota. Google a veces avisa de esto y a veces no; destildarlo
> evita el rebote.

Volvé al panel: el archivo ya te aparece **en la lista**. Hacé clic y listo.

> No hay que pegar ningún link. La lista muestra todo lo que le compartiste al
> panel, con el más reciente arriba, y tiene un buscador por nombre.
>
> Esa lista además contesta sola la pregunta que más se hace acá: *¿lo compartí
> bien?*. Si el archivo está en la lista, sí. Si no está, falta compartirlo — o
> se lo compartiste a otra dirección.
>
> (Si preferís pegar el link, el link sigue estando: abajo de la lista, en
> *"O pegar el link a mano"*.)

---

## Si algo no anda

| Lo que dice el panel | Qué pasó |
|---|---|
| *El archivo no está compartido con la cuenta del panel* | Falta el paso de compartir, o se compartió otro archivo. Fijate de haber pegado la dirección **completa** (termina en `.iam.gserviceaccount.com`). |
| *Falta activar la API de Google en el proyecto* | Te salteaste el paso 2. Fijate que estén las **tres**: Sheets, Docs y Drive. |
| *No pude leer la lista* | Casi siempre falta la **Google Drive API** (paso 2). El resto anda igual: podés pegar el link a mano mientras tanto. |
| *Ese es un archivo de credenciales de usuario…* | Bajaste el archivo del lugar equivocado. Tiene que salir de **Cuentas de servicio → Claves**, no de "ID de cliente de OAuth". |
| *Google rechazó la firma… fijate el reloj* | La hora o la fecha de esta computadora están mal. Google rechaza los pedidos que vienen del futuro o de muy atrás. Corregí la hora de Windows y probá de nuevo. |
| *Ese documento no tiene ninguna tabla adentro* | Le pegaste el link de un Google Doc sin tablas. Un reporte necesita datos en filas y columnas. |

---

## Lo que el panel puede y no puede hacer

**Puede:** leer las planillas y documentos que le compartas, y ver el nombre y
la fecha de esos mismos archivos para armar la lista.

**No puede:** escribir, modificar, borrar, ni ver ningún otro archivo de tu
Drive. Los permisos que pide son de solo lectura, y además solo alcanza a lo
que le compartiste explícitamente. Si le sacás el acceso a un archivo desde
Drive, deja de verlo en el acto.

**Dónde quedan los datos:** en esta computadora. El panel lee la planilla,
arma el tablero y el reporte, y nada de eso viaja a la intranet de vendedores
salvo los números que vos prendas uno por uno.

---

## La otra forma de conectar

En la pantalla hay un link que dice *"Conectar de la otra forma (con el
navegador)"*. Ese es un camino anterior, que sigue funcionando para quien ya lo
tenga configurado. Tiene tres inconvenientes que el de arriba no tiene:

- Hay que crear un cliente de OAuth y copiar dos claves al panel.
- Google avisa que *"no verificó esta aplicación"* y hay que entrar a
  Configuración avanzada para seguir.
- Mientras el proyecto esté en modo prueba, **el permiso se vence a los 7
  días** y el panel deja de leer sin que nadie haya tocado nada.

Si estás empezando de cero, usá la cuenta de servicio.
