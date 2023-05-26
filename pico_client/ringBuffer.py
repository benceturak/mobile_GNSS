
class RingBufferException(Exception):
    pass

class RingBuffer:
    def __init__(self, bufferSize = 10000) -> None:
        self.buffer = bytearray(bufferSize)
        self.startIdx = 0
        self.endIdx = 0
        self.size = 0

    def size(self) -> int:
        return self.size
    
    def capacity(self) -> int:
        return len(self.buffer)

    def isFull(self) -> bool:
        return len(self.buffer) == self.size
    
    def putFrom(self, data, fromIdx, toIdx, preventOverwrite = False) -> None:
        putLen = toIdx - fromIdx
        if putLen == 0:
            return
        
        if preventOverwrite and self.isFull():
            raise RingBufferException("Cannot add data to full RingBuffer")

        elif self.endIdx < self.startIdx:
            # ring buffer overlaps
            if preventOverwrite and self.startIdx - self.endIdx < putLen:
                raise RingBufferException("Data ({} B) doesn't fit in RingBuffer ({} B available)".format(putLen, self.startIdx - self.endIdx))
            
            self.buffer[self.endIdx : self.endIdx + putLen] = data[fromIdx : toIdx]
            self.endIdx += putLen
            self.startIdx = max(self.startIdx, self.endIdx)

        else:
            # ring buffer does not overlap (yet?)
            if len(self.buffer) - self.endIdx >= putLen:
                # new data fits until end of buffer                
                self.buffer[self.endIdx : self.endIdx + putLen] = data[fromIdx : toIdx]
                self.endIdx = (self.endIdx + putLen) % len(self.buffer)

            else:
                # new data doesn't fit after endIdx, have to splice it and make ring buffer overlap
                if preventOverwrite and len(self.buffer) - (self.endIdx - self.startIdx) < putLen:
                    raise RingBufferException("Data ({} B) doesn't fit in RingBuffer ({} B available)".format(putLen, len(self.buffer) - (self.endIdx - self.startIdx)))

                bytesFitTillEnd = len(self.buffer) - self.endIdx
                self.buffer[self.endIdx : len(self.buffer)] = data[fromIdx : fromIdx + bytesFitTillEnd]

                bytesRemaining = putLen - bytesFitTillEnd
                self.buffer[0 : bytesRemaining] = data[fromIdx + bytesFitTillEnd : toIdx]
                self.endIdx = bytesRemaining
                self.startIdx = max(self.startIdx, self.endIdx)
        
        self.size = min(self.size + putLen, self.capacity())
    
    def popInto(self, buffer, fromIdx, maxBytes = 0) -> int:

        if maxBytes == 0 or maxBytes > self.size:
            maxBytes = self.size

        if self.startIdx < self.endIdx:
            # no overlapping
            bytesToPop = min(self.size, maxBytes)
            buffer[fromIdx : fromIdx + bytesToPop + 1] = self.buffer[self.startIdx : self.startIdx + bytesToPop]
            
            if bytesToPop == self.size:
                # buffer becomes empty, start from 0 for sanity :)
                self.startIdx = 0
                self.endIdx = 0
            else:
                self.startIdx += bytesToPop

            self.size -= bytesToPop

        else:
            # overlapping
            bytesAtEnd = len(self.buffer) - self.startIdx
            bytesToPopFromEnd = min(bytesAtEnd, maxBytes)
            buffer[fromIdx : fromIdx + bytesToPopFromEnd] = self.buffer[self.startIdx : self.startIdx + bytesToPopFromEnd]

            bytesToPopFromStart = maxBytes - bytesToPopFromEnd
            if bytesToPopFromStart > 0:
                buffer[fromIdx + bytesToPopFromEnd : fromIdx + bytesToPopFromEnd + bytesToPopFromStart] = self.buffer[0 : bytesToPopFromStart]

            bytesToPop = bytesToPopFromStart + bytesToPopFromEnd
            if bytesToPop == self.size:
                # buffer becomes empty, start from 0 for sanity :)
                self.startIdx = 0
                self.endIdx = 0
            else:
                if bytesToPopFromStart > 0:
                    self.startIdx = bytesToPopFromStart
                else:
                    self.startIdx += bytesToPopFromEnd
            
            self.size -= bytesToPop
        
        return maxBytes

    def __str__(self) -> str:
        if self.size == 0:
            return str(self.buffer[0:0])
        elif self.startIdx < self.endIdx:
            return str(self.buffer[self.startIdx : self.endIdx])
        else:
            return str(self.buffer[self.startIdx : len(self.buffer)] + self.buffer[0 : self.endIdx])
        
    def rawStr(self) -> str:
        return str(self.buffer) + " [{}][{}:{}]".format(self.size, self.startIdx, self.endIdx)

'''
rb = RingBuffer(10000)
b = bytearray(100)
b[0:10] = b'\x01\x01\x01\x01\x01\x01\x01\x01\x01\x01'
rb.putFrom(b, 0, 10)
b[0:10] = b'\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00'
len = rb.popInto(b, 0)
print(b[0:len])
'''
