import readchar
import time
messages = open("processed_result").read().split('\n')
state = [int(x) for x in open("mark").read().split()]
ind = len(state)

def save():
    open("mark", "w").write('\n'.join([str(x) for x in state]))

UP = 5
SZ = 20

def update():
    global state
    print("\x1b[H\x1b[3J", end="")
    print(f"Press q to quit, k to go up, j to down, l to toggle mark. Progress: {ind}/{len(messages)}, " + "{:.2f}".format(ind/len(messages) * 100) + "%")
    state += [0] * max(0, ind - len(state) + 1 + SZ)
    up = max(0, ind - UP)
    for i in range(SZ):
        if i + up >= len(messages):
            break
        print(("*" if i + up == ind else " ") + " " + ("tox" if state[i + up] else "ok ") + " " + messages[i + up] + '\n')
    print("\x1b[2;1H", end="")

while True:
    update()
    c = readchar.readchar()
    if c == 'q':
        save()
        print('\x1b[H\x1b[3J', end="")
        break
    if c == 'l':
        state[ind] = 1 - state[ind]
    if c == 'k':
        ind = max(0, ind - 1)
    if c == 'j':
        ind = min(len(messages), ind + 1)
    time.sleep(0.05)
