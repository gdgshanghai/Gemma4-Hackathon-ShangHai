import struct, sys

PATH = "/root/Gemma/gguf/gemma-4-E4B-it-Q4_K_M.gguf"

GGUF_MAGIC = 0x46554747
# value type ids
T = {0:'u8',1:'i8',2:'u16',3:'i16',4:'u32',5:'i32',6:'f32',7:'bool',8:'str',9:'arr',10:'u64',11:'i64',12:'f64'}

f = open(PATH,'rb')
def rd(fmt):
    sz = struct.calcsize(fmt)
    return struct.unpack(fmt, f.read(sz))

magic, = rd('<I')
assert magic == GGUF_MAGIC, magic
version, = rd('<I')
n_tensors, = rd('<Q')
n_kv, = rd('<Q')

def rstr():
    n, = rd('<Q')
    return f.read(n).decode('utf-8','replace')

def rval(t):
    if t==8: return rstr()
    if t==4: return rd('<I')[0]
    if t==5: return rd('<i')[0]
    if t==10: return rd('<Q')[0]
    if t==11: return rd('<q')[0]
    if t==6: return rd('<f')[0]
    if t==12: return rd('<d')[0]
    if t==7: return rd('<?')[0]
    if t==0: return rd('<B')[0]
    if t==1: return rd('<b')[0]
    if t==2: return rd('<H')[0]
    if t==3: return rd('<h')[0]
    if t==9:
        et, = rd('<I'); cnt, = rd('<Q')
        return [rval(et) for _ in range(cnt)]
    raise ValueError(t)

want = {}
for _ in range(n_kv):
    key = rstr()
    t, = rd('<I')
    v = rval(t)
    if any(k in key for k in ('chat_template','tokenizer.ggml.bos','tokenizer.ggml.eos','general.architecture')):
        want[key] = v

for k,v in want.items():
    if 'chat_template' in k:
        print('==== %s ====' % k)
        print(v)
    else:
        print('%s = %s' % (k, v))
