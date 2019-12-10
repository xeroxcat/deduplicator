import os,sys
import filecmp
import csv
import zlib
from collections import namedtuple
from datetime import datetime

SCAN_RECORD = '.deduplicator_record'
PREV_SCAN_RECORD = '.deduplicator_record_prev'
RECORD_FIELDNAMES = ['name', 'size', 'csum', 'm_time', 'dups']
FileRecord = namedtuple('FileRecord', RECORD_FIELDNAMES)

def main():
    path_arg = sys.argv[1]
    #print(path)
    recrScan(path_arg)

def recrScan(root, rescan=False):
    # check for an existing SCAN_RECORD
    dedup_record_path = os.path.join(root, SCAN_RECORD)
    if os.path.isfile(dedup_record_path):
        if rescan == True:
            pass
            #rename SCAN_RECORD to PREV_SCAN_RECORD and delete SCAN_RECORD
        else:
            return
    else:
        print(dedup_record_path, 'doesn\'t exist! (new dir found)')

    # build SCAN_RECORD in 'root'
    dir_list, file_list, sym_list = scanDir(root)
    # 1) make sure subdirectories have SCAN_RECORDs
    for dir_entry in dir_list:
        recrScan(dir_entry.path, rescan=rescan)
    # 2) fill initial SCAN_RECORD for this folder
    fr_list = [fileData(dir_entry) for dir_entry in file_list]
    fr_list.sort(key=lambda x: x.size)
    #for fr in fr_list:
    #    print(fr.size, fr.csum, fr.name, datetime.fromtimestamp(fr.m_time))
    listToFile(dedup_record_path, fr_list)

def listToFile(save_path, filerecord_list):
    """save a list of FileRecord objects to save_path/SCAN_RECORD

    Assume save_path points to a directory. Clobber any existing
    SCAN_RECORD
    """
    #file_path = os.path.join(save_path, SCAN_RECORD)
    print(save_path)
    try:
        with open(save_path, mode='w', newline='') as scanrecord_csv:
            writer = csv.DictWriter(scanrecord_csv, fieldnames=RECORD_FIELDNAMES)
            for filerecord in filerecord_list:
                writer.writerow(filerecord._asdict())
                print(filerecord._asdict())
    except Exception as e:
        print(e)
        
def fileData(dir_entry):
    """return a FileRecord of the corresponding directory entry

    Assume dir_entry points to a file. Populate 'dups' field w/ empty list
    """
    file_stat = dir_entry.stat()
    return FileRecord(name=dir_entry.name, size=file_stat.st_size
            , csum=crc32(dir_entry.path)
            , m_time=file_stat.st_mtime, dups=[])

def crc32(filename):
    """open specified file and calculate crc32, return as hex string

    copied from CrouZ's answer: 
    stackoverflow.com/questions/1742866/compute-crc-of-file-in-python
    """
    fh = open(filename, 'rb')
    result = 0
    while True:
        #read in 64 kb chunks
        s = fh.read(65536)
        if not s:
            break
        result = zlib.crc32(s, result)
    fh.close()
    #print(hex(result))
    #return "%08X" % (result & 0xFFFFFFFF)
    return result

def scanDir(root):
    """return a 3-tuple of directories, files, and symlinks in dir_path

    each item is a list of dirEntry objects as returned by os.scanDir()
    entries in directories and files are not symbolic links. 
    entries in symlinks may link to either directories or files
    """
    dir_list = os.scandir(root)
    directories = []
    files = []
    symlinks = []
    for entry in dir_list:
        if entry.is_dir(follow_symlinks=False):
            directories.append(entry)
        elif entry.is_file(follow_symlinks=False):
            files.append(entry)
        elif entry.is_symlink():
            symlinks.append(entry)
    return (directories, files, symlinks)
    
#older functions below
def recPrint(root, indent=''): 
    print(indent + root)
    indent += '|'
    os.listdir(root)
    file_list = []
    dir_list = []
    for dir_entry in os.listdir(root):
        entry_path = os.path.join(root,dir_entry)
        if os.path.isfile(entry_path):
            file_list.append(dir_entry)
        if os.path.isdir(entry_path):
            dir_list.append(entry_path)
    for file_entry in file_list:
        print(indent + file_entry)
    else:
        print(indent + '_')
    for dir_entry in dir_list:
        recPrint(dir_entry, indent)

def walkPath(path_str):
    """Return list of all files in path_str and subdirectories
    
    Each item in returned list is a tuple (file_name, file_size, file_path)
    """
    walk_item = os.walk(path_str)
    file_list = []
    #print(walk_item)
    #print(repr(walk_item))
    for root, dirs, files in walk_item:
        #print(root, "\ndir list:", dirs, "\nfile list:", files)
        for file_entry in files:
            file_path = os.path.join(root,file_entry)
            file_size = os.path.getsize(file_path)
            file_list.append((file_entry, file_size, file_path))
    return file_list

def condenseFileList(file_list):
    condensed_list = [file_list.pop(0)]
    for f_name, f_size, f_path in file_list:
        if f_size == 0:
            condensed_list.append((f_name, f_size, f_path))
            continue
        other_name, other_size, other_path = condensed_list[-1]
        if f_size == other_size:
            if type(other_path) is list:
                print('aa')
                print('**', other_path[0], f_path)
                if filecmp.cmp(other_path[0], f_path, shallow=False):
                    condensed_list[-1] = (other_name.append(f_name),
                            f_size, other_path.append(f_path))
                continue
            else:
                print('bb')
                print(other_path, f_path)
                if filecmp.cmp(other_path, f_path, shallow=False):
                    condensed_list[-1] = ([other_name, f_name],
                            f_size, [other_path, f_path])
                    continue
        condensed_list.append((f_name, f_size, f_path))
    return condensed_list

if __name__ == '__main__':
    main()
