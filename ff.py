import re


f = open("./qqah")
line = f.readline()

f1 = open("./q8","a+")

#pattern = re.compile(r"1\d{10}")
#匹配手机号
pattern = re.compile(r"[0-9]*----[0-9]*----[0-9]*")
while line:
    
    string = pattern.match(line)
    if string == None:
        #print("no")
        f1.write(line)
        #f1.close()
    else:
        #print(string)
        char_t = "----"
        n = line.find(char_t)

        ll = line[n+4:]
        f1.write(ll)
        #f1.close()
    line = f.readline()
f.close()
f1.close()

