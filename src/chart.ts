import * as d3 from 'd3'

interface Margin {
  top: number
  right: number
  bottom: number
  left: number
}

export interface Config {
  margin: Margin
  width: number
  height: number
  duration: number
  domain: [number, number]
  xlabel: string
  ylabel: string
}

type Datum = [Date, number]

type Selection = d3.Selection<d3.BaseType, Datum[], HTMLElement, any>
type ValueFn = d3.ValueFn<d3.BaseType, unknown, d3.KeyType>

export function streamingChart(config?: Config) {
  let margin = config?.margin || {top: 20, right: 20, bottom: 60, left: 60}
  let width = config?.width || 600
  let height = config?.height || 400
  let duration = config?.duration || 200
  let yDomain = config?.domain || [-1, 1]
  let xlabel = config?.xlabel || "x"
  let ylabel = config?.ylabel || "y"

  let x = d3.scaleUtc()
  let y = d3.scaleLinear()

  function chart(selection: Selection) {
    selection.each(function(data: Datum[]) {

      // Update the scales.
      let xDomain = d3.extent(
        data,
        (d: Datum) => d[0],
      ).map(v => v!)
      x
        .domain(xDomain)
        .range([0, width - margin.left - margin.right])
      y
        .domain(yDomain)
        .range([height - margin.top - margin.bottom, 0])

      // Create the skeletal chart if necessary.
      let gEnter = d3.select(this).selectAll("svg")
          .data([data])
          .enter()
        .insert("svg", ":nth-child(2)")
          .attr("preserveAspectRatio", "xMidYMid meet")
        .append("g")
      gEnter
        .append("g")
          .attr("class", "x axis")
      gEnter
        .append("g")
        .append("text")
          .attr("x", (width - margin.left - margin.right) / 2)
          .attr("y", height - margin.bottom / 2)
          .attr("text-anchor", "start")
          .attr("fill", "#888")
          .text(xlabel)
      gEnter
        .append("g")
          .attr("class", "y axis")
      gEnter
        .append("g")
        .append("text")
          .attr("x", -(height - margin.top - margin.bottom) / 2)
          .attr("y", -margin.left / 2)
          .attr("text-anchor", "start")
          .attr("fill", "#888")
          .attr("transform", "rotate(-90)")
          .text(ylabel)
      gEnter
        .append("defs").append("clipPath")
          .attr("id", "clip")
        .append("rect")
          .attr("width", width - margin.left - margin.right)
          .attr("height", height - margin.top - margin.bottom)
      gEnter
        .append("g")
          .attr("clip-path", "url(#clip)")
          .attr("class", "data")
          .attr("fill", "none")
          .attr("stroke-linecap", "round")

      // Update the out dimensions.
      let svg = d3.select(this).select("svg")
          .attr("viewBox", `0 0 ${width} ${height}`)

      // Update the inner dimensions.
      let g = svg.select("g")
          .attr("transform", `translate(${margin.left},${margin.top})`)

      // Update the line path.
      svg.select("g.data").selectAll("path")
          .data(data, ((d: [number, number]) => d[0]) as ValueFn)
          .join(
            enter => enter.append("path")
              .attr("d", d => (
                `M${x(new Date(d[0].getTime() + duration))},${y(d[1])}h0`
              ))
              .attr("stroke", "blue")
              .attr("stroke-width", 5)
              .call(enter => enter.transition()
                .duration(duration)
                .ease(d3.easeLinear)
                .attr("d", d => `M${x(d[0])},${y(d[1])}h0`)
              ),
            update => update
              .call(update => update.transition()
                .duration(duration)
                .ease(d3.easeLinear)
                .attr("d", d => `M${x(d[0])},${y(d[1])}h0`)
              ),
          )

      // Update the axes.
      g.select<SVGGElement>(".x.axis")
          .attr("transform", `translate(0,${y.range()[0]})`)
          .transition().duration(duration).ease(d3.easeLinear)
          .call(d3.axisBottom(x).ticks(5))
      g.select<SVGGElement>(".y.axis")
          .call(d3.axisLeft(y).ticks(5))
    })
  }

  return chart
}
