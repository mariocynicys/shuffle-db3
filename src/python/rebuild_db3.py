#!/usr/bin/env python
# -*- coding: iso-8859-1

# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 59 Temple Place, Suite 330, Boston, MA  02111-1307  USA

__title__="KeyJ's iPod shuffle Database Builder"
__version__="1.0-rc1"
__author__="Martin Fiedler"
__email__="martin.fiedler@gmx.net"

""" VERSION HISTORY
1.0-rc1 (2006-04-26)
    * finally(!) added the often-requested auto-rename feature (-r option)
0.7-pre1 (2005-06-09)
    * 0.6-final was skipped because of the huge load of new (experimental)
      features in this version :)
    * rule files allow for nice and flexible fine tuning
    * fixed --nochdir and --nosmart bugs
    * numerical sorting (i.e. "track2.mp3" < "track10.mp3")
    * iTunesSD entries are now copied over from the old file if possible; this
      should preserve the keys for .aa files
0.6-pre2 (2005-05-02)
    * fixed file type bug (thanks to Nowhereman)
    * improved audio book support (thanks to Nowhereman)
    * files called $foo.book.$type (like example.book.mp3) are stored as
      audio books now
    * the subdirectories of /iPod_Control/Music are merged as if they were a
      single directory
0.6-pre1 (2005-04-23)
    * always starts from the directory of the executable now
    * output logging
    * generating iTunesPState and iTunesStats so that the iPod won't overwrite
      iTunesShuffle anymore
    * -> return of smart shuffle ;)
    * directory display order is identical to playback ordernow
    * command line options and help
    * interactive mode, configurable playback volume, directory limitation
0.5 (2005-04-15)
    * major code refactoring (thanks to Andre Kloss)
    * removed "smart shuffle" again -- the iPod deleted the file anyway :(
    * common errors are now reported more concisely
    * dot files (e.g. ".hidden_file") are now ignored while browsing the iPod
0.4 (2005-03-20)
    * fixed iPod crashes after playing the shuffle playlist to the end
    * fixed incorrect databse entries for non-MP3 files
0.3 (2005-03-18)
    * Python version now includes a "smart shuffle" feature
0.2 (2005-03-15)
    * added Python version
0.1 (2005-03-13)
    * initial public release, Win32 only
"""


import sys,os,os.path,array,getopt,random,types,fnmatch,operator,string,eyed3
from functools import cmp_to_key, reduce

KnownProps=('filename','size','ignore','type','shuffle','reuse','bookmark')
Rules=[
  ([('filename','~','*.mp3')],          {'type':1, 'shuffle':1, 'bookmark':0}),
  ([('filename','~','*.m4?')],          {'type':2, 'shuffle':1, 'bookmark':0}),
  ([('filename','~','*.m4b')],          {          'shuffle':0, 'bookmark':1}),
  ([('filename','~','*.aa')],           {'type':1, 'shuffle':0, 'bookmark':1, 'reuse':1}),
  ([('filename','~','*.wav')],          {'type':4, 'shuffle':0, 'bookmark':0}),
  ([('filename','~','*.book.???')],     {          'shuffle':0, 'bookmark':1}),
  ([('filename','~','*.announce.???')], {          'shuffle':0, 'bookmark':0}),
  ([('filename','~','/recycled/*')],    {'ignore':1}),
]

Options={
  "volume":None,
  "interactive":False,
  "smart":True,
  "home":True,
  "logging":True,
  "reuse":1,
  "logfile":"rebuild_db.log.txt",
  "rename":False
}
domains=[]
total_count=0
KnownEntries={}


################################################################################


def open_log():
  global logfile
  if Options['logging']:
    try:
      logfile=open(Options['logfile'],"w")
    except IOError:
      logfile=None
  else:
   logfile=None


def log(line="",newline=True):
  global logfile
  if newline:
    print (line)
    line+="\n"
  else:
    print (line)
    line+=" "
  if logfile:
    try:
      logfile.write(line)
    except IOError:
      pass


def close_log():
  global logfile
  if logfile:
    logfile.close()


def go_home():
  if Options['home']:
    try:
      os.chdir(os.path.split(sys.argv[0])[0])
    except OSError:
      pass


def filesize(filename):
  try:
    return os.stat(filename)[6]
  except OSError:
    return None


################################################################################


def MatchRule(props,rule):
  try:
    prop,op,ref=props[rule[0]],rule[1],rule[2]
  except KeyError:
    return False
  if rule[1]=='~':
    return fnmatch.fnmatchcase(prop.lower(),ref.lower())
  elif rule[1]=='=':
    return cmp(prop,ref)==0
  elif rule[1]=='>':
    return cmp(prop,ref)>0
  elif rule[1]=='<':
    return cmp(prop,ref)<0
  else:
    return False


def ParseValue(val):
  if len(val)>=2 and ((val[0]=="'" and val[-1]=="'") or (val[0]=='"' and val[-1]=='"')):
    return val[1:-1]
  try:
    return int(val)
  except ValueError:
    return val

def ParseRule(rule):
  sep_pos=min([rule.find(sep) for sep in "~=<>" if rule.find(sep)>0])
  prop=rule[:sep_pos].strip()
  if not prop in KnownProps:
    log("WARNING: unknown property `%s'"%prop)
  return (prop,rule[sep_pos],ParseValue(rule[sep_pos+1:].strip()))

def ParseAction(action):
  prop,value=map(string.strip,action.split('=',1))
  if not prop in KnownProps:
    log("WARNING: unknown property `%s'"%prop)
  return (prop,ParseValue(value))

def ParseRuleLine(line):
  line=line.strip()
  if not(line) or line[0]=="#":
    return None
  try:
    # split line into "ruleset: action"
    tmp=line.split(":")
    ruleset=map(string.strip,":".join(tmp[:-1]).split(","))
    actions=dict(map(ParseAction,tmp[-1].split(",")))
    if len(ruleset)==1 and not(ruleset[0]):
      return ([],actions)
    else:
      return (map(ParseRule,ruleset),actions)
  except OSError: #(ValueError,IndexError,KeyError):
    log("WARNING: rule `%s' is malformed, ignoring"%line)
    return None
  return None


################################################################################


def safe_char(c):
  if c in "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_":
    return c
  return "_"

def rename_safely(path,name):
  base,ext=os.path.splitext(name)
  newname=''.join(map(safe_char,base))
  if name==newname+ext:
    return name
  if os.path.exists("%s/%s%s"%(path,newname,ext)):
    i=0
    while os.path.exists("%s/%s_%d%s"%(path,newname,i,ext)):
      i+=1
    newname+="_%d"%i
  newname+=ext
  try:
    os.rename("%s/%s"%(path,name),"%s/%s"%(path,newname))
  except OSError:
    pass  # don't fail if the rename didn't work
  return newname


def write_to_db(filename):
  global iTunesSD,domains,total_count,KnownEntries,Rules

  # set default properties
  props={
    'filename': filename,
    'size': filesize(filename[1:]),
    'ignore': 0,
    'type': 1,
    'shuffle': 1,
    'reuse': Options['reuse'],
    'bookmark': 0
  }

  # check and apply rules
  for ruleset,action in Rules:
    if reduce(operator.__and__,[MatchRule(props,rule) for rule in ruleset],True):
      props.update(action)
  if props['ignore']: return 0

  # retrieve entry from known entries or rebuild it
  entry=props['reuse'] and (filename in KnownEntries) and KnownEntries[filename]
  if not entry:
    header[29]=props['type']
    entry=bytes(header)+ \
      b"".join([bytes(c,"utf-8") +b"\0" for c in filename[:261]])+ \
      b"\0"*(525-2*len(filename))

  # write entry, modifying shuffleflag and bookmarkflag at least
  log("=> %s"%(filename))
  b = entry[:555]+bytes(chr(props['shuffle']), "utf-8")+bytes(chr(props['bookmark']), "utf-8")+entry[557:558]
  iTunesSD.write(b)
  if props['shuffle']: domains[-1].append(total_count)
  total_count+=1
  return 1


def make_key(s):
  if not s: return s
  s=s.lower()
  for i in range(len(s)):
    if s[i].isdigit(): break
  if not s[i].isdigit(): return s
  for j in range(i,len(s)):
    if not s[j].isdigit(): break
  if s[j].isdigit(): j+=1
  return (s[:i],int(s[i:j]),make_key(s[j:]))

def key_repr(x):
  if type(x)==types.TupleType:
    return "%s%d%s"%(x[0],x[1],key_repr(x[2]))
  else:
    return x

def cmp(a, b):
  return (a > b) - (a < b) 

def cmp_key(a,b):
  if type(a)==tuple and type(b)==tuple:
    if (a[3]==-1 or b[3]==-1):
      return cmp(a[0],b[0]) or cmp(a[1],b[1]) or cmp_key(a[2],b[2])
    else:
      return cmp(a[4]*100+a[3],b[4]*100+b[3])
  else:
    return cmp(key_repr(a),key_repr(b))


def file_entry(path,name,prefix=""):
  if not(name) or name[0]==".": return None
  fullname="%s/%s"%(path,name)
  may_rename=not(fullname.startswith("./iPod_Control")) and Options['rename']
  try:
    if os.path.islink(fullname):
      return None
    if os.path.isdir(fullname):
      if may_rename: name=rename_safely(path,name)
      return (0,make_key(name),prefix+name)
    if os.path.splitext(name)[1].lower() in (".mp3",".m4a",".m4b",".m4p",".aa",".wav"):
      if may_rename: name=rename_safely(path,name)
      return (1,make_key(name),prefix+name)
  except OSError:
    pass
  return None


def browse(path, interactive):
  global domains

  if path[-1]=="/": path=path[:-1]
  displaypath=path[1:]
  if not displaypath: displaypath="/"

  if interactive:
    while 1:
      try:
        choice=raw_input("include `%s'? [(Y)es, (N)o, (A)ll] "%displaypath)[:1].lower()
      except EOFError:
        raise KeyboardInterrupt
      if not choice: continue
      if choice in "at":    # all/alle/tous/<dontknow>
        interactive=0
        break
      if choice in "yjos":  # yes/ja/oui/si
        break
      if choice in "n":     # no/nein/non/non?
        return 0

  try:
    files=filter(None,[file_entry(path,name) for name in os.listdir(path)])
  except OSError:
    return

  if path=="./iPod_Control/Music":
    subdirs=[x[2] for x in files if not x[0]]
    files=filter(lambda x: x[0], files)
    for dir in subdirs:
      subpath="%s/%s"%(path,dir)
      try:
        files.extend(filter(lambda x: x and x[0],[file_entry(subpath,name,dir+"/") for name in os.listdir(subpath)]))
      except OSError:
        pass
 
  newfiles=[] 
  for file in files:
    if file[0]==1:
      audiofile=eyed3.load("%s/%s"%(path, file[2]))
      if not audiofile is None and not audiofile.tag is None and not audiofile.tag.track_num[0] is None:
        track_num=audiofile.tag.track_num[0]
      else:
        track_num=-1
      if not audiofile is None and not audiofile.tag is None and not audiofile.tag.disc_num[0] is None:
        disk_num=audiofile.tag.disc_num[0]
      else:
        disk_num=1
    else:
      track_num=-2
      disk_num=0
    newfile=(file[0], file[1], file[2], track_num, disk_num)
    newfiles.append(newfile)
 
  files=newfiles 
  files.sort(key=cmp_to_key(cmp_key))
  count=len([None for x in files if x[0]])
  if count: domains.append([])

  real_count=0
  for item in files:
    fullname="%s/%s"%(path,item[2])
    #log("=> %s: Disk #%d, Track #%d"%(fullname, item[4], item[3]))
    if item[0]:
      real_count+=write_to_db(fullname[1:])
    else:
      browse(fullname,interactive)

  if real_count==count:
    log("%s: %d files"%(displaypath,count))
  else:
    log("%s: %d files (out of %d)"%(displaypath,real_count,count))


################################################################################


def stringval(i):
  if i<0: i+=0x1000000
  return b"%c%c%c"%(i&0xFF,(i>>8)&0xFF,(i>>16)&0xFF)

def listval(i):
  if i<0: i+=0x1000000
  return [i&0xFF,(i>>8)&0xFF,(i>>16)&0xFF]


def make_playback_state(volume=None):
  # I'm not at all proud of this function. Why can't stupid Python make strings
  # mutable?!
  log("Setting playback state ...",False)
  PState=[]
  try:
    f=open("iPod_Control/iTunes/iTunesPState","rb")
    a=f.read()
    PState=list(a)
    f.close()
  except (IOError,EOFError):
    del PState[:]
  if len(PState)!=21:
    PState=listval(29)+[0]*15+listval(1)  # volume 29, FW ver 1.0
  PState[3:15]=[0]*6+[1]+[0]*5  # track 0, shuffle mode, start of track
  if volume is not None:
    PState[:3]=listval(volume)
  try:
    f=open("iPod_Control/iTunes/iTunesPState","wb")
    array.array('B',PState).tofile(f)
    f.close()
  except IOError:
    log("FAILED.")
    return 0
  log("OK.")
  return 1


def make_stats(count):
  log("Creating statistics file ...",False)
  try:
    open("iPod_Control/iTunes/iTunesStats","wb").write(\
         stringval(count)+b"\0"*3+(stringval(18)+b"\xff"*3+b"\0"*12)*count)
  except IOError:
    log("FAILED.")
    return 0
  log("OK.")
  return 1


################################################################################


def smart_shuffle():
  try:
    slice_count=max(map(len,domains))
  except ValueError:
    return []
  slices=[[] for x in range(slice_count)]
  slice_fill=[0]*slice_count

  for d in range(len(domains)):
    used=[]
    if not domains[d]: continue
    for n in domains[d]:
      # find slices where the nearest track of the same domain is far away
      metric=[min([slice_count]+[min(abs(s-u),abs(s-u+slice_count),abs(s-u-slice_count)) for u in used]) for s in range(slice_count)]
      thresh=(max(metric)+1)/2
      farthest=[s for s in range(slice_count) if metric[s]>=thresh]

      # find emptiest slices
      thresh=(min(slice_fill)+max(slice_fill)+1)/2
      emptiest=[s for s in range(slice_count) if slice_fill[s]<=thresh if (s in farthest)]

      # choose one of the remaining candidates and add the track to the chosen slice
      s=random.choice(emptiest or farthest)
      slices[s].append((n,d))
      slice_fill[s]+=1
      used.append(s)

  # shuffle slices and avoid adjacent tracks of the same domain at slice boundaries
  seq=[]
  last_domain=-1
  for slice in slices:
    random.shuffle(slice)
    if len(slice)>2 and slice[0][1]==last_domain:
      slice.append(slice.pop(0))
    seq+=[x[0] for x in slice]
    last_domain=slice[-1][1]
  return seq


def make_shuffle(count):
  random.seed()
  if Options['smart']:
    log("Generating smart shuffle sequence ...",False)
    seq=smart_shuffle()
  else:
    log("Generating shuffle sequence ...",False)
    seq=range(count)
    random.shuffle(seq)
  try:
    open("iPod_Control/iTunes/iTunesShuffle","wb").write(b"".join(map(stringval,seq)))
  except IOError:
    log("FAILED.")
    return 0
  log("OK.")
  return 1


################################################################################


def main(dirs):
  global header,iTunesSD,total_count,KnownEntries,Rules
  log("Welcome to %s, version %s"%(__title__,__version__))
  log()

  try:
    f=open("rebuild_db.rules","r")
    Rules+=filter(None,map(ParseRuleLine,f.read().split("\n")))
    f.close()
  except IOError:
    pass

  if not os.path.isdir("iPod_Control/iTunes"):
    log("""ERROR: No iPod control directory found!
Please make sure that:
 (*) this program's working directory is the iPod's root directory
 (*) the iPod was correctly initialized with iTunes""")
    sys.exit(1)

  header=array.array('B')
  iTunesSD=None
  try:
    iTunesSD=open("iPod_Control/iTunes/iTunesSD","rb")
    header.fromfile(iTunesSD,51)
    if Options['reuse']:
      iTunesSD.seek(18)
      entry=iTunesSD.read(558)
      while len(entry)==558:
        filename=entry[33::2].split(b"\0",1)[0]
        KnownEntries[filename]=entry
        entry=iTunesSD.read(558)
  except (IOError,EOFError):
    pass
  if iTunesSD: iTunesSD.close()

  if len(header)==51:
    log("Using iTunesSD headers from existing database.")
    if KnownEntries:
      log("Collected %d entries from existing database."%len(KnownEntries))
  else:
    del header[18:]
    if len(header)==18:
      log("Using iTunesSD main header from existing database.")
    else:
      del header[:]
      log("Rebuilding iTunesSD main header from scratch.")
      header.fromlist([0,0,0,1,6,0,0,0,18]+[0]*9)
    log("Rebuilding iTunesSD entry header from scratch.")
    header.fromlist([0,2,46,90,165,1]+[0]*20+[100,0,0,1,0,2,0])

  log()
  try:
    iTunesSD=open("iPod_Control/iTunes/iTunesSD","wb")
    header[:18].tofile(iTunesSD)
  except IOError:
    log("""ERROR: Cannot write to the iPod database file (iTunesSD)!
Please make sure that:
 (*) you have sufficient permissions to write to the iPod volume
 (*) you are actually using an iPod shuffle, and not some other iPod model :)""")
    sys.exit(1)
  del header[:18]

  log("Searching for files on your iPod.")
  try:
    if dirs:
      for dir in dirs:
        browse("./"+dir,Options['interactive'])
    else:
      browse(".",Options['interactive'])
    log("%d playable files were found on your iPod."%total_count)
    log()
    log("Fixing iTunesSD header.")
    iTunesSD.seek(0)
    iTunesSD.write(b"\0%c%c"%(total_count>>8,total_count&0xFF))
    iTunesSD.close()
  except IOError:
    log("ERROR: Some strange errors occured while writing iTunesSD.")
    log("       You may have to re-initialize the iPod using iTunes.")
    sys.exit(1)

  if make_playback_state(Options['volume'])* \
     make_stats(total_count)* \
     make_shuffle(total_count):
    log()
    log("The iPod shuffle database was rebuilt successfully.")
    log("Have fun listening to your music!")
  else:
    log()
    log("WARNING: The main database file was rebuilt successfully, but there were errors")
    log("         while resetting the other files. However, playback MAY work correctly.")


################################################################################


def help():
  print ("Usage: %s [OPTION]... [DIRECTORY]..."%sys.argv[0])
  print ("""Rebuild iPod shuffle database.

Mandatory arguments to long options are mandatory for short options too.
  -h, --help         display this help text
  -i, --interactive  prompt before browsing each directory
  -v, --volume=VOL   set playback volume to a value between 0 and 38
  -s, --nosmart      do not use smart shuffle
  -n, --nochdir      do not change directory to this scripts directory first
  -l, --nolog        do not create a log file
  -f, --force        always rebuild database entries, do not re-use old ones
  -L, --logfile      set log file name

Must be called from the iPod's root directory. By default, the whole iPod is
searched for playable files, unless at least one DIRECTORY is specified.""")


def opterr(msg):
  print ("parse error:",msg)
  print ("use `%s -h' to get help"%sys.argv[0])
  sys.exit(1)

def parse_options():
  try:
    opts,args=getopt.getopt(sys.argv[1:],"hiv:snlfL:r",\
              ["help","interactive","volume=","nosmart","nochdir","nolog","force","logfile=","rename"])
  except getopt.GetoptError as message:
    opterr(message)
  for opt,arg in opts:
    if opt in ("-h","--help"):
      help()
      sys.exit(0)
    elif opt in ("-i","--interactive"):
      Options['interactive']=True
    elif opt in ("-v","--volume"):
      try:
        Options['volume']=int(arg)
      except ValueError:
        opterr("invalid volume")
    elif opt in ("-s","--nosmart"):
      Options['smart']=False
    elif opt in ("-n","--nochdir"):
      Options['home']=False
    elif opt in ("-l","--nolog"):
      Options['logging']=False
    elif opt in ("-f","--force"):
      Options['reuse']=0
    elif opt in ("-L","--logfile"):
      Options['logfile']=arg
    elif opt in ("-r","--rename"):
      Options['rename']=True
  return args


################################################################################


if __name__=="__main__":
  args=parse_options()
  go_home()
  open_log()
  try:
    main(args)
  except KeyboardInterrupt:
    log()
    log("You decided to cancel processing. This is OK, but please note that")
    log("the iPod database is now corrupt and the iPod won't play!")
  close_log()
