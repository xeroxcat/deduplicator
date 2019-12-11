import os,sys
import filecmp
import csv
import zlib
from collections import namedtuple
from datetime import datetime
from pathlib import Path
from operator import itemgetter
import yaml

SCAN_RECORD = '.deduplicator_record'
PREV_SCAN_RECORD = '.deduplicator_record_prev'
SCAN_SUMMARY = 'deduplicator_summary'
PREV_SCAN_SUMMARY = 'deduplicator_summary_prev'
RECORD_FIELDNAMES = ['name', 'size', 'csum', 'm_time', 'dups']
FileRecord = namedtuple('FileRecord', RECORD_FIELDNAMES)

def main():
    path_arg = sys.argv[1]
    
    # build a list of files in each directory
    recrScan(path_arg)
    
    # add duplicates to each scan record
    file_dict = recrDupSearch(path_arg)

    # write summary for found duplicates
    writeSummary(path_arg, file_dict)

def writeSummary(s_path, file_dict):
    dup_list = []
    unique_list = []
    for (chksm, size), dups in file_dict.items():
        if len(dups) > 1:
            for path in dups:
                #name = os.path.basename(path)
                dup_list.append((path, size, chksm))
        else:
            #name = os.path.basename(dups[0])
            unique_list.append((dups[0], size, chksm))
    
    dup_list.sort(key=itemgetter(1), reverse=True)
    unique_list.sort(key=itemgetter(1), reverse=True)
    with open(os.path.join(s_path,SCAN_SUMMARY), 'w', newline='') as sum_file:
        yaml.dump_all((dup_list, unique_list), sum_file)

    #print('duplicate list')
    print(yaml.dump_all((dup_list, unique_list)))
    #print('unique list')
    #print(*unique_list, sep='\n')


def recrDupSearch(path):
    dir_list, _, _ = scanDir(path)
    subdir_file_dict = {}
    for dir_entry in dir_list:
        mergeFileDict(subdir_file_dict, recrDupSearch(dir_entry.path))
    resaveScanRecord(path, subdir_file_dict)

    #margin_len = path.count('/')
    #margin = ''
    #for i in range(margin_len):
    #    margin = margin + ' '
    #print(margin+path)
    #print(margin+str(empty_file_list), *local_file_dict.items()
    #        , sep='\n'+margin)
    local_file_dict = loadScanRecordAsDict(path)
    mergeFileDict(local_file_dict, subdir_file_dict)
    return local_file_dict

def resaveScanRecord(path, subdir_file_dict):
    record_path = os.path.join(path, SCAN_RECORD)
    fr_list = []
    with open(record_path, newline='') as scanrecord_csv:
        reader = csv.DictReader(scanrecord_csv, fieldnames=RECORD_FIELDNAMES)
        for row in reader:
            fr = FileRecord(row['name'], int(row['size']), int(row['csum'])
                , float(row['m_time']), [])
            fr_list.append(fr)
    for fr in fr_list:
        if fr.size == 0:
            continue
        if (fr.csum, fr.size) in subdir_file_dict:
            dup_list = subdir_file_dict[fr.csum, fr.size]
            for dup_path in dup_list:
                dup_relpath = os.path.relpath(dup_path, path)
                fr.dups.append(dup_relpath)
    listToFile(record_path, fr_list)

def loadScanRecordAsDict(path):
    """load a SCAN_RECORD in directory 'path' and return entries as dict

    exclude all empty files. Keys in dict are tuples (file_chksum, file_size)
    and values are singleton lists of relative paths to each file.
    """
    record_path = os.path.join(path, SCAN_RECORD)
    file_dict = {}
    #empty_file_list = []
    with open(record_path, newline='') as scanrecord_csv:
        reader = csv.DictReader(scanrecord_csv, fieldnames=RECORD_FIELDNAMES)
        for row in reader:
            file_path = os.path.join(path, row['name'])
            if row['size'] != '0':
            #    empty_file_list.append(file_path)
            #else:
            #    file_dict.update({(int(row['csum']), int(row['size'])): 
            #        [file_path]})
                mergeFileDict(file_dict,
                        {(int(row['csum']), int(row['size'])): [file_path]})
    return file_dict

def mergeFileDict(root_dict, sub_dict):
    """modify root_dict to add items from sub_dict. assume values are lists.
    
    if a key exists in both, extend value of the key in root_dict with the 
    value in sub_dict
    """
    for key, paths in sub_dict.items():
        if key in root_dict:
            r_paths = root_dict[key]
            r_paths.extend(paths)
        else:
            root_dict.update({key: paths})

def recrScan(root, rescan=True):
    """store a csv SCAN_RECORD at path 'root' and in all of its subdirectories

    fields defined by RECORD_FIELDNAMES, rows list each file located in the
    directory. dups field is not populated.
    """
    # check for an existing SCAN_RECORD
    dedup_record_path = os.path.join(root, SCAN_RECORD)
    if os.path.isfile(dedup_record_path):
        if rescan == True:
            old_path = os.path.join(root, PREV_SCAN_RECORD)
            os.replace(dedup_record_path, old_path)
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
    listToFile(dedup_record_path, fr_list)

def listToFile(save_path, filerecord_list):
    """save a list of FileRecord objects to save_path/SCAN_RECORD

    Assume save_path points to a directory. Clobber any existing
    SCAN_RECORD
    """
    #print(save_path)
    with open(save_path, mode='w', newline='') as scanrecord_csv:
        writer = csv.DictWriter(scanrecord_csv, fieldnames=RECORD_FIELDNAMES)
        for filerecord in filerecord_list:
            writer.writerow(filerecord._asdict())
        
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
    entries with name matching SCAN_RECORD are not included in file list
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
            if (entry.name != SCAN_RECORD
                    and entry.name != PREV_SCAN_RECORD):
                files.append(entry)
        elif entry.is_symlink():
            symlinks.append(entry)
    return (directories, files, symlinks)
    
if __name__ == '__main__':
    main()
