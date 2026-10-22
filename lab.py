import re

start_keywords = ["CREATE", "INSERT", "PRINT_TREE", "CONTAINS", "SEARCH"]
SEG_RE = r'\[\s*(-?\d+)\s*,\s*(-?\d+)\s*\]'

class Node:
    def __init__(self, leaf, items=None):
        # leaf = true => items - segments
        # leaf = false => items - nodes
        # lo - min of child lows, hi - max of child highs
        self.leaf = leaf
        self.items = items or []
        self.lo = self.hi = None
        self.recalc()

    def recalc(self):
        if self.leaf:
            self.lo = min(s[0] for s in self.items)
            self.hi = max(s[1] for s in self.items)
        else:
            self.lo = min(c.lo for c in self.items)
            self.hi = max(c.hi for c in self.items)

# helper functions for rtree
def str_seg(l, h):
    return f"[{l}, {h}]"

def enlargement(node, seg):
    new_lo = min(node.lo, seg[0])
    new_hi = max(node.hi, seg[1])
    return (new_hi - new_lo) - (node.hi - node.lo)

def segment_matches(seg, kind, a, b):
    l, h = seg
    if kind is None:
        return True
    if kind == "CONTAINS":
        return l <= a and b <= h
    if kind == "INTERSECTS":
        return l <= b and a <= h
    if kind == "LEFT_OF":
        return h <= a
    raise ValueError(kind)
 
def may_match(node, kind, a, b):
    if kind is None:
        return True
    if kind == "CONTAINS":
        return node.lo <= a and b <= node.hi
    if kind == "INTERSECTS":
        return node.lo <= b and a <= node.hi
    if kind == "LEFT_OF":
        return node.lo <= a
    raise ValueError(kind)

def choose_child(node, seg):
    best = None
    best_cost = None
    for child in node.items:
        cost = (enlargement(child, seg), child.hi - child.lo)
        if best is None or cost < best_cost:
            best = child
            best_cost = cost
    return best

def parse_segment(token):
    m = re.fullmatch(SEG_RE, token)
    if m is None:
        return None
    return int(m[1]), int(m[2])

class RTree:
    def __init__(self):
        self.root = None
    
    def insert(self, seg):

        if self.contains(seg):
            return False

        if self.root is None:
            self.root = Node(True, [seg])
            return True

        sibling = self._insert(self.root, seg)
        if sibling is not None:
            self.root = Node(False, [self.root, sibling])
        return True

    def _insert(self, node, seg):
        if node.leaf:
            node.items.append(seg)
        else:
            child = choose_child(node, seg)
            sibling = self._insert(child, seg)
            if sibling is not None:
                node.items.append(sibling)
        node.recalc()
        if len(node.items) > 2:
            return self.split(node)
        return None

    def split(self, node):
        if node.leaf:
            node.items.sort()
        else:
            node.items.sort(key=lambda n: (n.lo, n.hi))
        mid = len(node.items) // 2
        right = Node(node.leaf, node.items[mid:])
        node.items = node.items[:mid]
        node.recalc()
        return right

    def contains(self, seg):
        l, h = seg
        return seg in self.search("CONTAINS", l, h)

    def search(self, kind=None, l=None, h=None):
        result = []
        if self.root is not None:
            self.collect(self.root, kind, l, h, result)
        return result

    def collect(self, node, kind, l, h, result):
        for item in node.items:
            if node.leaf:
                if segment_matches(item, kind, l, h):
                    result.append(item)
            else:
                if may_match(item, kind, l, h):
                    self.collect(item, kind, l, h, result)

    def format_tree(self):
        if self.root is None:
            return "(empty)"
        lines = [str_seg(self.root.lo, self.root.hi)]
        self.lines(self.root, "", lines)
        return "\n".join(lines)
    def lines(self, node, prefix, out):
        for i, item in enumerate(node.items):
            last = i == len(node.items) - 1
            branch = "└── " if last else "├── "
            if node.leaf:
                out.append(prefix + branch + str_seg(*item))
            else:
                out.append(prefix + branch + str_seg(item.lo, item.hi))
                self.lines(item, prefix + ("    " if last else "│   "), out)

sets = {}

def syntacsis_check(tokens):

    if not tokens: 
        pass

    if len(tokens) < 2:
        print("Занадто мало аргументів.")
        return 0

    command = tokens[0].upper()
    name = tokens[1]

    if command not in start_keywords:
        print(f"Недійсне ключове слово {tokens[0]}")
        return 0

    if not re.fullmatch(r'[a-zA-Z][a-zA-Z0-9_]*', name):
        print(f"Ім'я таблиці {name} не відповідає формату [a-zA-Z][a-zA-Z0-9_]*")
        return 0

    if command == start_keywords[0]: #CREATE
        if (len(tokens) > 2):
            print(f"Команда {command} приймає лише 2 аргументи (отримано {len(tokens)}).")
            return 0
        if name in sets:
            print(f"Множина {name} вже існує.")
            return 0
        sets[name] = RTree()
        print(f"Множина {name} успішно створена.")
        return 1
    
    if name not in sets:
        print(f"Множини {name} не існує.")
        return 0
    
    if command == start_keywords[1]: #INSERT
        if len(tokens)!= 3:
            print(f"Команда {command} приймає лише 3 аргументи (отримано {len(tokens)}).")
            return 0
        seg = parse_segment(tokens[2])
        if seg is None:
            print(f"Очікувався відрізок у форматі [l, h] (отримано {tokens[2]}).")
            return 0
        low, high = seg
        if low > high:
            print(f"Нижня границя ({low}) не повинна бути більшою за верхню ({high})")
            return 0
        if sets[name].insert((low, high)):
            print(f"Відрізок {low}, {high} успішно вставлено.")
        else:
            print(f"Відрізок {low}, {high} вже є в множині.")        
        return 1

    if command == start_keywords[2]: #PRINT_TREE
        if (len(tokens) > 2):
            print(f"Команда {command} приймає лише 2 аргументи (отримано {len(tokens)}).")
            return 0
        print(sets[name].format_tree())
        return 1

    if command == start_keywords[3]: #CONTAINS
        if len(tokens) != 3:
            print(f"Команда {command} приймає лише 3 аргументи (отримано {len(tokens)}).")
            return 0
        seg = parse_segment(tokens[2])
        if seg is None:
            print(f"Очікувався відрізок у форматі [l, h] (отримано {tokens[2]}).")
            return 0
        low, high = seg
        if low > high:
            print(f"Нижня границя ({low}) не повинна бути більшою за верхню ({high})")
            return 0
        print("TRUE" if sets[name].contains(seg) else "FALSE")
        return 1
    
    if command == start_keywords[4]: #SEARCH
        if len(tokens) == 2:
            kind, l, h = None, None, None
        elif len(tokens) == 5:
            if tokens[2].upper() != "WHERE":
                print(f"Не знайдене ключове слово WHERE (отримано {tokens[2]}).")
                return 0
            query = tokens[3].upper()
            if query == "LEFT_OF":
                try:
                    x = int(tokens[4])
                except ValueError:
                    print(f"{tokens[4]} має бути числом.")
                    return 0
                kind, l, h = "LEFT_OF", x, None
            elif query in ["CONTAINS", "INTERSECTS"]:
                seg = parse_segment(tokens[4])
                if seg is None:
                    print(f"Очікувався відрізок у форматі [l, h] (отримано {tokens[4]}).")
                    return 0
                low, high = seg
                if low > high:
                    print(f"Нижня границя ({low}) не повинна бути більшою за верхню ({high})")
                    return 0
                kind, l, h = query, low, high
            else:
                print(f"Невідомий запит {tokens[3]} (очікувалось CONTAINS, INTERSECTS або LEFT_OF).")
                return 0
        else:
            print(f"Команда {command} приймає 2 або 5 аргументів (отримано {len(tokens)}).")
            return 0
        found = sets[name].search(kind, l, h)
        print("\n".join(str_seg(*s) for s in sorted(found)) or "Відрізків не знайдено.")
        return 1

def main():
    while True:
        try:
            string = input('> ')
            while ';' not in string:
                string += ' ' + input('... ')
        except EOFError:
            break
        string = string.partition(';')[0]

        tokens = [t.group() for t in re.finditer(SEG_RE + r'|\S+', string)]
        
        syntacsis_check(tokens)

main()
