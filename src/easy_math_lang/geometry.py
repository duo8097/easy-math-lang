import re
import math
import numpy as np

def split_args(args_str):
    parts = []
    current = []
    depth = 0
    for char in args_str:
        if char == '(':
            depth += 1
        elif char == ')':
            depth -= 1
        
        if char == ';' and depth == 0:
            parts.append(''.join(current).strip())
            current = []
        else:
            current.append(char)
    parts.append(''.join(current).strip())
    return parts

class GeometrySolver:
    def __init__(self):
        self.points = {} # name -> [x, y]
        self.fixed = set()
        self.constraints = [] # list of lambda P: cost
        self.draw_commands = [] # list of (cmd, args)
        
    def add_point(self, name, x=None, y=None):
        if name not in self.points:
            if x is not None and y is not None:
                self.points[name] = np.array([float(x), float(y)])
                self.fixed.add(name)
            else:
                self.points[name] = np.random.randn(2) * 5
                
    def solve(self):
        # We use a simple gradient descent with momentum
        lr = 0.01
        momentum = 0.9
        velocity = {p: np.zeros(2) for p in self.points if p not in self.fixed}
        
        def compute_cost_and_grad():
            cost = 0
            grads = {p: np.zeros(2) for p in self.points if p not in self.fixed}
            
            # small repulsion to prevent points from collapsing if unconstrained
            # for p1 in self.points:
            #     for p2 in self.points:
            #         if p1 < p2:
            #             d = np.linalg.norm(self.points[p1] - self.points[p2])
            #             if d < 0.1:
            #                 cost += 1.0
            
            # Numeric gradient
            eps = 1e-5
            
            def eval_constraints(pts):
                c = 0
                for constr in self.constraints:
                    c += constr(pts)
                return c

            base_cost = eval_constraints(self.points)
            cost += base_cost
            
            for p in self.points:
                if p in self.fixed: continue
                
                orig = self.points[p].copy()
                
                self.points[p][0] += eps
                cx = eval_constraints(self.points)
                self.points[p][0] = orig[0]
                
                self.points[p][1] += eps
                cy = eval_constraints(self.points)
                self.points[p][1] = orig[1]
                
                grads[p][0] = (cx - base_cost) / eps
                grads[p][1] = (cy - base_cost) / eps
                
            return cost, grads
            
        for step in range(5000):
            cost, grads = compute_cost_and_grad()
            if cost < 1e-4:
                break
            for p in self.points:
                if p not in self.fixed:
                    velocity[p] = momentum * velocity[p] - lr * grads[p]
                    self.points[p] += velocity[p]

def norm(v):
    return np.linalg.norm(v)

def cross2d(v1, v2):
    return v1[0]*v2[1] - v1[1]*v2[0]

def angle_between(v1, v2):
    n1 = norm(v1)
    n2 = norm(v2)
    if n1 < 1e-5 or n2 < 1e-5: return 0
    return math.acos(np.clip(np.dot(v1, v2)/(n1*n2), -1.0, 1.0))


def parse_draw_block(block_text):
    solver = GeometrySolver()
    
    # Extract commands like *point(...) etc
    pattern = re.compile(r'\*([a-zA-Z0-9-]+)\((.*?)\)')
    
    for match in pattern.finditer(block_text):
        cmd = match.group(1)
        args_str = match.group(2)
        args = split_args(args_str)
        
        if cmd == 'point':
            if '=' in args[0]:
                name, coords = args[0].split('=')
                name = name.strip()
                x, y = coords.split(',')
                solver.add_point(name, float(x.strip()), float(y.strip()))
            else:
                name = args[0].strip()
                solver.add_point(name)
        elif cmd == 'distance':
            A, B, d = [a.strip() for a in args]
            solver.add_point(A)
            solver.add_point(B)
            solver.constraints.append(lambda P, a=A, b=B, d=float(d): (norm(P[a] - P[b]) - d)**2)
        elif cmd == 'perp':
            # perp(A; B; C; D) -> AB perp CD
            if len(args) == 4:
                A, B, C, D = [a.strip() for a in args]
                for pt in [A,B,C,D]: solver.add_point(pt)
                solver.constraints.append(lambda P, a=A, b=B, c=C, d=D: np.dot(P[b]-P[a], P[d]-P[c])**2)
            elif len(args) == 3:
                # perp(A; B; C) -> AB perp BC
                A, B, C = [a.strip() for a in args]
                for pt in [A,B,C]: solver.add_point(pt)
                solver.constraints.append(lambda P, a=A, b=B, c=C: np.dot(P[b]-P[a], P[c]-P[b])**2)
        elif cmd == 'parallel':
            A, B, C, D = [a.strip() for a in args]
            for pt in [A,B,C,D]: solver.add_point(pt)
            solver.constraints.append(lambda P, a=A, b=B, c=C, d=D: cross2d(P[b]-P[a], P[d]-P[c])**2)
        elif cmd == 'on-line':
            A, B, C = [a.strip() for a in args]
            for pt in [A,B,C]: solver.add_point(pt)
            solver.constraints.append(lambda P, a=A, b=B, c=C: cross2d(P[b]-P[a], P[c]-P[a])**2)
        elif cmd == 'on-circle':
            O, r, A = [a.strip() for a in args]
            for pt in [O,A]: solver.add_point(pt)
            solver.constraints.append(lambda P, o=O, r=float(r), a=A: (norm(P[a]-P[o]) - r)**2)
        elif cmd == 'equal-length':
            A, B, C, D = [a.strip() for a in args]
            for pt in [A,B,C,D]: solver.add_point(pt)
            solver.constraints.append(lambda P, a=A, b=B, c=C, d=D: (norm(P[b]-P[a]) - norm(P[d]-P[c]))**2)
        elif cmd == 'midpoint':
            A, B, C = [a.strip() for a in args]
            for pt in [A,B,C]: solver.add_point(pt)
            solver.constraints.append(lambda P, a=A, b=B, c=C: norm(P[c] - (P[a]+P[b])/2)**2)
        elif cmd == 'intersection':
            C = args[0].strip()
            # args[1] = line(A, B), args[2] = line(D, E)
            def parse_line(l):
                m = re.match(r'line\((.*?);(.*?)\)', l.strip())
                return m.group(1).strip(), m.group(2).strip()
            A, B = parse_line(args[1])
            D, E = parse_line(args[2])
            for pt in [A,B,C,D,E]: solver.add_point(pt)
            solver.constraints.append(lambda P, a=A, b=B, c=C: cross2d(P[b]-P[a], P[c]-P[a])**2)
            solver.constraints.append(lambda P, d=D, e=E, c=C: cross2d(P[e]-P[d], P[c]-P[d])**2)
            
        solver.draw_commands.append((cmd, args))
        
    solver.solve()
    return generate_typst(solver)

def generate_typst(solver):
    lines = []
    lines.append("#import \"@preview/cetz:0.3.1\"")
    lines.append("#align(center)[#cetz.canvas({")
    lines.append("  import cetz.draw: *")
    
    # First, setup points (if we need to use them via cetz coordinates, but we have numbers)
    # Actually we can just hardcode the numbers.
    # To keep code clean we can define named coords in CetZ
    # wait, CetZ doesn't have a simple let for coords inside canvas, but we can just interpolate.
    
    # We will compute the bounding box to center/scale if needed, but CetZ handles bounding box.
    for p, coord in solver.points.items():
        lines.append(f'  circle(({coord[0]:.3f}, {coord[1]:.3f}), radius: 0.05, fill: black, name: "{p}")')
        lines.append(f'  content("{p}", [{p}], anchor: "south-west", padding: 0.1)')
        
    for cmd, args in solver.draw_commands:
        if cmd == 'triangle':
            A, B, C = [a.strip() for a in args[:3]]
            lines.append(f'  line("{A}", "{B}", "{C}", close: true)')
        elif cmd == 'line':
            A, B = [a.strip() for a in args[:2]]
            lines.append(f'  line("{A}", "{B}")')
        elif cmd == 'ray':
            A, B = [a.strip() for a in args[:2]]
            lines.append(f'  line("{A}", "{B}")') # simple approximation
        elif cmd == 'circle':
            center = args[0].strip()
            if len(args) == 2:
                r_or_pt = args[1].strip()
                if r_or_pt in solver.points:
                    lines.append(f'  circle("{center}", radius: "{r_or_pt}")') # Wait, cetz circle takes distance? 
                    # actually we can compute the distance in python
                    d = norm(solver.points[center] - solver.points[r_or_pt])
                    lines.append(f'  circle("{center}", radius: {d:.3f})')
                else:
                    lines.append(f'  circle("{center}", radius: {float(r_or_pt)})')
        elif cmd == 'right-angle':
            # A, B, C -> right angle at A (or B? rule.txt says right-angle(B ; A ; C) -> right angle at A)
            if len(args) == 3:
                B, A, C = [a.strip() for a in args]
                                # A manual right angle mark
                
    
    lines.append("})]")
    return "\n".join(lines)
