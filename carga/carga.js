// =====================================================================
// carga.js  -  Usuarios simulados comprando en Online Boutique (k6)
//
// Usa tasa de llegada CONSTANTE: llegan N "clientes" por segundo aunque el
// sistema este fallando. Asi la falla no reduce artificialmente la carga
// (evita el sesgo de "omision coordinada") y la curva F(t) refleja lo que
// viviria un usuario real.
//
// Cada iteracion = un cliente: portada -> producto -> agrega al carro -> ve carro.
// Todas las paginas consultan cartservice (contador del carro), por eso una
// falla en cartservice afecta toda la experiencia de compra.
// =====================================================================
import http from 'k6/http';

const BASE = __ENV.BASE_URL || 'http://localhost:8080';
const PRODUCTOS = [
  'OLJCESPC7Z', '66VCHSJNUP', '1YMWWN1N4O', 'L9ECAV7KIM', '2ZYFJ3GM2N',
  '0PUK6V6EV0', 'LS4PSXUNUM', '9SIQT8TOJO', '6E92ZMYYFZ',
];

export const options = {
  scenarios: {
    compras: {
      executor: 'constant-arrival-rate',
      rate: Number(__ENV.TASA || 5),     // clientes por segundo
      timeUnit: '1s',
      duration: __ENV.DURACION || '360s',
      preAllocatedVUs: 20,
      maxVUs: 150,
    },
  },
  discardResponseBodies: true,
};

function p(nombre, extra) {
  return Object.assign({ timeout: '5s', tags: { name: nombre } }, extra || {});
}

export default function () {
  const prod = PRODUCTOS[Math.floor(Math.random() * PRODUCTOS.length)];
  http.get(`${BASE}/`, p('inicio'));
  http.get(`${BASE}/product/${prod}`, p('producto'));
  // POST responde 302 -> /cart; no seguimos la redireccion para medirla aparte
  http.post(`${BASE}/cart`, { product_id: prod, quantity: '1' }, p('agregar_carro', { redirects: 0 }));
  http.get(`${BASE}/cart`, p('ver_carro'));
}
