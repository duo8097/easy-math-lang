#set text(size: 12pt)
#set page(paper: "a4", margin: 2cm)
#align(center)[= Easy Math Document]

#import "@preview/cetz:0.4.2"
#align(center)[#cetz.canvas({
  import cetz.draw: *
  circle((0.000, 0.000), radius: 0.05, fill: black, name: "A")
  content("A", [A], anchor: "north-east", padding: 0.12)
  circle((4.000, 0.000), radius: 0.05, fill: black, name: "B")
  content("B", [B], anchor: "west", padding: 0.12)
  circle((0.030, 3.000), radius: 0.05, fill: black, name: "C")
  content("C", [C], anchor: "south-east", padding: 0.12)
  line("A", "B", "C", close: true)
  line((0.200, 0.000), (0.202, 0.200), (0.002, 0.200))
  content((2.000, 0.180), [#"4"])
  content((-0.165, 1.502), [#"3"])
})] \
#v(0.65em)
#import "@preview/cetz:0.4.2"
#align(center)[#cetz.canvas({
  import cetz.draw: *
  circle((0.000, 0.000), radius: 0.05, fill: black, name: "D")
  content("D", [D], anchor: "north-east", padding: 0.12)
  circle((6.000, 0.000), radius: 0.05, fill: black, name: "E")
  content("E", [E], anchor: "north-west", padding: 0.12)
  circle((3.001, 4.011), radius: 0.05, fill: black, name: "F")
  content("F", [F], anchor: "south", padding: 0.12)
  line("D", "E", "F", close: true)
  arc((3.001, 4.011), start: 233.19deg, stop: 306.79deg, radius: 0.400)
  content((3.001, 3.331), [#"60°"])
})] \
#v(0.65em)
#import "@preview/cetz:0.4.2"
#align(center)[#cetz.canvas({
  import cetz.draw: *
  circle((0.000, 0.000), radius: 0.05, fill: black, name: "O")
  content("O", [O], anchor: "north", padding: 0.12)
  circle((-1.015, 2.821), radius: 0.05, fill: black, name: "P")
  content("P", [P], anchor: "south", padding: 0.12)
  circle((5.170, 4.980), radius: 0.05, fill: black, name: "Q")
  content("Q", [Q], anchor: "west", padding: 0.12)
  circle("O", radius: 3.000)
  line("O", "P")
  line("P", "Q")
})] \
