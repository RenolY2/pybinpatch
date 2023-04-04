import struct 
import hashlib 
import binascii

def read_uint32_at(data, offset):
    return struct.unpack_from("I", data, offset)[0]


class UnsupportedFormat(Exception):
    pass 

    
class WrongSourceFile(Exception):
    pass 


class FaultyPatch(Exception):
    pass


class DiffPatch(object):
    def __init__(self, file_size):
        self.hash_src = None
        self.hash_target = None
        self.file_size = file_size
        self.replacements = []
        self.additions = b""
    
    @classmethod
    def from_difference(cls, source, target):
        patch = cls(len(target))
        
        last_patch_offset = None
        last_patch_data = []
        
        patch.hash_src = hashlib.sha1(source).digest()
        patch.hash_target = hashlib.sha1(target).digest()
         
        
        # Record the changes within the file 
        for i in range(min(len(source), len(target))):
            if source[i] != target[i]:
                # Add changes onto the last change chain
                if last_patch_offset is None:
                    last_patch_offset = i 
                last_patch_data.append(target[i:i+1])
                
            elif last_patch_offset is not None:
                # Finish the last change chain
                patch.replacements.append((last_patch_offset, b"".join(last_patch_data)))
                last_patch_offset = None
                del last_patch_data
                last_patch_data = []
        
        if last_patch_offset is not None:
            patch.replacements.append((last_patch_offset, b"".join(last_patch_data)))
            
        if len(target) > len(source):
            patch.additions = target[len(source):]
        
        return patch 
    
    @classmethod
    def from_patch(cls, f):
        if f.read(16) != b"Simple Patch Fmt":
            raise UnsupportedFormat("Not A Supported Patch Format!")
        hash_src = f.read(20)
        hash_target = f.read(20)
        filesize = struct.unpack("I", f.read(4))[0]
        
        patch = cls(filesize)
        patch.hash_src = hash_src
        patch.hash_target = hash_target
        
        replace_count = struct.unpack("I", f.read(4))[0]
        for i in range(replace_count):
            offset, datalength = struct.unpack("II", f.read(8))
            data = f.read(datalength)
            patch.replacements.append((offset, data))
        
        additions_length = struct.unpack("I", f.read(4))[0]
        patch.additions = f.read(additions_length)
        
        return patch
    
    def write(self, out):
        out.write(b"Simple Patch Fmt")
        out.write(self.hash_src)
        out.write(self.hash_target)
        out.write(struct.pack("I", self.file_size))
        
        out.write(struct.pack("I", len(self.replacements)))
        # Write the data replacements 
        for offset, data in self.replacements:
            out.write(struct.pack("II", offset, len(data)))
            out.write(data)
        
        # Write Additional Data
        out.write(struct.pack("I", len(self.additions)))
        out.write(self.additions)
        
    
    def apply(self, source, out):
        src_hash = hashlib.sha1(source).digest()
        
        if src_hash != self.hash_src:
            raise WrongSourceFile("The patch doesn't fit the specified source file! \n"
                                    "Expected SHA-1 hash for source file: {0}".format(binascii.hexlify(self.hash_src)))
        
        out.write(source)
        #out.seek(len(source))
        out.write(self.additions)
        
            
        for offset, data in self.replacements:
        
            out.seek(offset)
            out.write(data)

        out.seek(self.file_size)
        out.truncate()
    
    
    def verify_result(self, out):
        out.seek(0)
        data = out.read()
        dst_hash = hashlib.sha1(data).digest() 
    
        if dst_hash != self.hash_target:
            raise WrongSourceFile("The patch result is wrong! The patch might be corrupted or it's a bug in the patch program. \n"
                                    "Expected SHA-1 for result file: {0}".format(binascii.hexlify(self.hash_target)))


if __name__ == "__main__":  
    import sys 
    if len(sys.argv) < 4 or sys.argv[1] not in ("patch", "create"):
        print("Usage:")
        print("Patching:")
        print("pybinpatch.py patch <original dol> <patch> [output]")
        print("Creating patch:")
        print("pybinpatch.py create <original dol> <patched dol> [output]" )
    else:
        
        action = sys.argv[1]
        in_file = sys.argv[2]
        in_file2 = sys.argv[3]
        if len(sys.argv) >= 5:
            out = sys.argv[4]
        else:
            if action == "patch":
                out = in_file+"_patched.bin"
            else:
                out = in_file+"_patch.bin"
        
        if action == "patch":
            with open(in_file, "rb") as f:
                data1 = f.read()
                
            with open(in_file2, "rb") as f:
                patch = DiffPatch.from_patch(f)
            
            with open(out, "wb") as f:
                patch.apply(data1, f)
                
            print("Saved patched dol to", out)
        if action == "create":
            with open(in_file, "rb") as f:
                data1 = f.read()
                  
            with open(in_file2, "rb") as f:
                data2 = f.read()
                        
            patch = DiffPatch.from_difference(data1, data2)
            
            with open(out, "wb") as f:
                patch.write(f)
                
            print("Saved patch to", out)