import os

def parse(s):
    res = [a[:a.find("</div>")].strip() for a in s.split("<div class=\"text\">")[1:]]
    #print(res)
    return res

res = []

for name in os.listdir():
    if name.startswith("messages"):
        res += parse(open(name).read())

open("result", "w").write('\n'.join(res))
