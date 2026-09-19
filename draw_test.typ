#set text(size: 12pt)
#set page(paper: "a4", margin: 2cm)
#align(center)[= Easy Math Document]

#import "@preview/cetz:0.4.2"
#align(center)[#cetz.canvas({
  import cetz.draw: *
  circle((0.000, 0.000), radius: 0.05, fill: black, name: "A")
  content("A", [A], anchor: "south-west", padding: 0.1)
  circle((4.000, 0.000), radius: 0.05, fill: black, name: "B")
  content("B", [B], anchor: "south-west", padding: 0.1)
  circle((0.001, -3.004), radius: 0.05, fill: black, name: "C")
  content("C", [C], anchor: "south-west", padding: 0.1)
  line("A", "B", "C", close: true)
  line((0.200, 0.000), (0.200, -0.200), (0.000, -0.200))
  // [planned] *length(A; B) not yet implemented
  // [planned] *length(A; C) not yet implemented
})] \
#v(0.65em)
#import "@preview/cetz:0.4.2"
#align(center)[#cetz.canvas({
  import cetz.draw: *
  circle((0.000, 0.000), radius: 0.05, fill: black, name: "D")
  content("D", [D], anchor: "south-west", padding: 0.1)
  circle((6.000, 0.000), radius: 0.05, fill: black, name: "E")
  content("E", [E], anchor: "south-west", padding: 0.1)
  circle((2.992, 4.002), radius: 0.05, fill: black, name: "F")
  content("F", [F], anchor: "south-west", padding: 0.1)
  line("D", "E", "F", close: true)
  // [planned] *angle(D; F; E; 60°) not yet implemented
})] \
#v(0.65em)
#import "@preview/cetz:0.4.2"
#align(center)[#cetz.canvas({
  import cetz.draw: *
  circle((0.000, 0.000), radius: 0.05, fill: black, name: "O")
  content("O", [O], anchor: "south-west", padding: 0.1)
  circle((-2.710, -1.277), radius: 0.05, fill: black, name: "P")
  content("P", [P], anchor: "south-west", padding: 0.1)
  circle((-2.631, -1.439), radius: 0.05, fill: black, name: "Q")
  content("Q", [Q], anchor: "south-west", padding: 0.1)
  circle("O", radius: 3.000)
  line("O", "P")
  line("P", "Q")
})] \
