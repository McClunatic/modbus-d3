import './style.css'
import { Config, streamingChart } from './chart'

import * as d3 from 'd3'

interface Response {
  x: number,
  y: number,
}

document.querySelector<HTMLDivElement>('#app')!.innerHTML = `
  <div>
    <h1>Vite + TypeScript</h1>
    <div class="card">
      <button id="start" type="button">Start</button>
      <button id="stop" type="button">Stop</button>
      <button id="reset" type="button">Reset</button>
    </div>
    <p id="latest" class="read-the-docs">
      Click on the Vite and TypeScript logos to learn more
    </p>
  </div>
`

let plot_data: Array<[Date, number]> = []

let duration = 200
let chart = streamingChart(({
  duration,
  xlabel: "t",
  ylabel: "sin(t)",
} as Config))

function updateChart(data: Response) {
  let data_point: [Date, number] = [new Date(data.x * 1000), data.y]
  plot_data.push(data_point)
  let s = data_point[1] < 0 ? '' : '+'
  let latest =
    `${data_point[0].toLocaleTimeString()}: ${s}${data_point[1].toFixed(2)}`
  document.getElementById("latest")!.textContent = latest
  document.title = latest
  if (plot_data.length > 50) plot_data.shift()
  d3.select("#app > div")
    .data([plot_data])
    .call(chart)
}

// let ws = new WebSocket('ws://localhost:8000/ws')

// ws.onmessage = (event) => {
//   let data = JSON.parse(event.data)
//   if (Object.keys(data).length === 0)
//     return
//   updateChart(data)
// }

if (window.Worker) {
  const worker = new Worker(new URL('./worker.js', import.meta.url))
  worker.onmessage = event => {
    updateChart(event.data)
  }
  document.getElementById("start")!.addEventListener("click", () => {
    worker.postMessage({running: true, duration: duration})
  })

  document.getElementById("stop")!.addEventListener("click", () => {
    worker.postMessage({running: false, duration: duration})
  })

  document.getElementById("reset")!.addEventListener("click", async () => {
    plot_data = []
    // ws.send(JSON.stringify({method: 'reset'}))
    await fetch('http://localhost:8000/reset')
  })
} else {
  console.log('Browser does not support web workers!')
}

// function updateInterval() {
//   if (!running)
//     return
//   fetch('http://localhost:8000/')
//     .then(response => response.json())
//     .then(data => updateChart(data))
// }

// setInterval(updateInterval, duration)