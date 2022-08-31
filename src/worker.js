let interval = null
let running = false

function getData() {
  if (!running)
    return
  fetch('http://localhost:8000/')
    .then(response => response.json())
    .then(data => postMessage(data))
}

onmessage = event => {
  running = event.data.running
  if (interval === null) {
    interval = setInterval(getData, event.data.duration)
  }
}
