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

let running = false;
let plot_data: Array<[Date, number]> = []

document.getElementById("start")!.addEventListener("click", () => {
  running = true
})

document.getElementById("stop")!.addEventListener("click", () => {
  running = false
})

document.getElementById("reset")!.addEventListener("click", async () => {
  plot_data = []
  await fetch('http://localhost:8000/reset')
})

let duration = 200
let chart = streamingChart(({
  duration,
  xlabel: "t",
  ylabel: "sin(t)",
} as Config))

while (true) {
  if (running) {
    let response = await fetch('http://localhost:8000/')
    let data: Response = await response.json()
    let data_point: [Date, number] = [new Date(data.x * 1000), data.y]
    plot_data.push(data_point)
    let s = data_point[1] < 0 ? '' : '+'
    document.getElementById("latest")!.textContent =
      `${data_point[0].toLocaleTimeString()}: ${s}${data_point[1].toFixed(2)}`
    if (plot_data.length > 50) plot_data.shift()
    d3.select("#app > div")
      .data([plot_data])
      .call(chart)
  }
  await new Promise(r => setTimeout(r, duration))
}