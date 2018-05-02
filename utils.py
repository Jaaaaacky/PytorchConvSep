import sys
import os,re
import collections
import csv
import soundfile as sf
import numpy as np
from scipy.stats import norm
import pyworld as pw
import matplotlib.pyplot as plt


import config

def stft(data, window=np.hanning(1024),
         hopsize=256.0, nfft=1024.0, fs=44100.0):
    """
    X, F, N = stft(data,window=sinebell(2048),hopsize=1024.0,
                   nfft=2048.0,fs=44100)
                   
    Computes the short time Fourier transform (STFT) of data.
    
    Inputs:
        data                  :
            one-dimensional time-series to be analyzed
        window=sinebell(2048) :
            analysis window
        hopsize=1024.0        :
            hopsize for the analysis
        nfft=2048.0           :
            number of points for the Fourier computation
            (the user has to provide an even number)
        fs=44100.0            :
            sampling rate of the signal
        
    Outputs:
        X                     :
            STFT of data
        F                     :
            values of frequencies at each Fourier bins
        N                     :
            central time at the middle of each analysis
            window
    """
    
    # window defines the size of the analysis windows
    lengthWindow = window.size
    
    lengthData = data.size
    
    # should be the number of frames by YAAFE:
    numberFrames = np.ceil(lengthData / np.double(hopsize)) + 2
    # to ensure that the data array s big enough,
    # assuming the first frame is centered on first sample:
    newLengthData = (numberFrames-1) * hopsize + lengthWindow

    # import pdb;pdb.set_trace()
    
    # !!! adding zeros to the beginning of data, such that the first window is
    # centered on the first sample of data

    # import pdb;pdb.set_trace()
    data = np.concatenate((np.zeros(int(lengthWindow/2)), data))
    
    # zero-padding data such that it holds an exact number of frames

    data = np.concatenate((data, np.zeros(int(newLengthData - data.size))))
    
    # the output STFT has nfft/2+1 rows. Note that nfft has to be an even
    # number (and a power of 2 for the fft to be fast)
    numberFrequencies = nfft / 2 + 1
    
    STFT = np.zeros([int(numberFrames), int(numberFrequencies)], dtype=complex)
    
    # storing FT of each frame in STFT:
    for n in np.arange(numberFrames):
        beginFrame = n*hopsize
        endFrame = beginFrame+lengthWindow
        frameToProcess = window*data[int(beginFrame):int(endFrame)]
        STFT[int(n),:] = np.fft.rfft(frameToProcess, np.int32(nfft), norm="ortho")
        
    # frequency and time stamps:
    F = np.arange(numberFrequencies)/np.double(nfft)*fs
    N = np.arange(numberFrames)*hopsize/np.double(fs)
    
    return STFT


def stft_stereo(data):
    assert data.shape[1] == 2
    stft_left = abs(stft(data[:,0]))
    stft_right = abs(stft(data[:,1]))
    return np.array([stft_left,stft_right])

def progress(count, total, suffix=''):
    bar_len = 60
    filled_len = int(round(bar_len * count / float(total)))

    percents = round(100.0 * count / float(total), 1)
    bar = '=' * filled_len + '-' * (bar_len - filled_len)

    sys.stdout.write('[%s] %s%s ...%s\r' % (bar, percents, '%', suffix))
    sys.stdout.flush()

def nan_helper(y):
    """Helper to handle indices and logical indices of NaNs.

    Input:
        - y, 1d numpy array with possible NaNs
    Output:
        - nans, logical indices of NaNs
        - index, a function, with signature indices= index(logical_indices),
          to convert logical indices of NaNs to 'equivalent' indices
    Example:
        >>> # linear interpolation of NaNs
        >>> nans, x= nan_helper(y)
        >>> y[nans]= np.interp(x(nans), x(~nans), y[~nans])
    """

    return np.isinf(y), lambda z: z.nonzero()[0]

def file_to_stft(input_file):
    audio,fs=sf.read(input_file)
    mixture=np.clip(audio[:,0]+audio[:,1],0.0,1.0)
    mix_stft=abs(stft(mixture))
    return mix_stft

def input_to_feats(input_file, mode=config.comp_mode):
    audio,fs=sf.read(input_file)
    vocals=np.array(audio[:,1])
    feats=pw.wav2world(vocals,fs,frame_period=5.80498866)

    ap = feats[2].reshape([feats[1].shape[0],feats[1].shape[1]]).astype(np.float32)
    ap = 10.*np.log10(ap**2)
    harm=10*np.log10(feats[1].reshape([feats[2].shape[0],feats[2].shape[1]]))

    y=69+12*np.log2(feats[0]/440)
    nans, x= nan_helper(y)
    naners=np.isinf(y)
    y[nans]= np.interp(x(nans), x(~nans), y[~nans])
    # y=[float(x-(min_note-1))/float(max_note-(min_note-1)) for x in y]
    y=np.array(y).reshape([len(y),1])
    guy=np.array(naners).reshape([len(y),1])
    y=np.concatenate((y,guy),axis=-1)

    if mode == 'mfsc':
        harmy=sp_to_mfsc(harm,60,0.45)
        apy=sp_to_mfsc(ap,4,0.45)
    elif mode == 'mgc':
        harmy=sp_to_mgc(harm,60,0.45)
        apy=sp_to_mgc(ap,4,0.45)


    out_feats=np.concatenate((harmy,apy,y.reshape((-1,2))),axis=1) 

    # harm_in=mgc_to_sp(harmy, 1025, 0.45)
    # ap_in=mgc_to_sp(apy, 1025, 0.45)


    return out_feats


def feats_to_audio(in_feats,filename, fs=config.fs,  mode=config.comp_mode):
    harm = in_feats[:,:60]
    ap = in_feats[:,60:-2]
    f0 = in_feats[:,-2:]
    f0[:,0] = f0[:,0]-69
    f0[:,0] = f0[:,0]/12
    f0[:,0] = 2**f0[:,0]
    f0[:,0] = f0[:,0]*440


    f0 = f0[:,0]*(1-f0[:,1])


    if mode == 'mfsc':
        harm = mfsc_to_mgc(harm)
        ap = mfsc_to_mgc(ap)


    harm = mgc_to_sp(harm, 1025, 0.45)
    ap = mgc_to_sp(ap, 1025, 0.45)

    harm = 10**(harm/10)
    ap = 10**(ap/20)

    y=pw.synthesize(f0.astype('double'),harm.astype('double'),ap.astype('double'),fs,5.80498866)
    sf.write(config.val_dir+filename+'.wav',y,fs)
    # return harm, ap, f0

def test(ori, re):
    plt.subplot(211)
    plt.imshow(ori.T,origin='lower',aspect='auto')
    plt.subplot(212)
    plt.imshow(re.T,origin='lower',aspect='auto')
    plt.show()


def generate_overlapadd(allmix,time_context=config.max_phr_len, overlap=config.max_phr_len/2,batch_size=config.batch_size):
    #window = np.sin((np.pi*(np.arange(2*overlap+1)))/(2.0*overlap))
    input_size = allmix.shape[-1]

    i=0
    start=0  
    while (start + time_context) < allmix.shape[0]:
        i = i + 1
        start = start - overlap + time_context 
    fbatch = np.zeros([int(np.ceil(float(i)/batch_size)),batch_size,time_context,input_size])+1e-10
    
    
    i=0
    start=0  

    while (start + time_context) < allmix.shape[0]:
        fbatch[int(i/batch_size),int(i%batch_size),:,:]=allmix[int(start):int(start+time_context),:]
        i = i + 1 #index for each block
        start = start - overlap + time_context #starting point for each block
    
    return fbatch,i

def overlapadd(fbatch,nchunks,overlap=int(config.max_phr_len/2)):

    input_size=fbatch.shape[-1]
    time_context=fbatch.shape[-2]
    batch_size=fbatch.shape[1]


    #window = np.sin((np.pi*(np.arange(2*overlap+1)))/(2.0*overlap))
    window = np.linspace(0., 1.0, num=overlap)
    window = np.concatenate((window,window[::-1]))
    #time_context = net.network.find('hid2', 'hh').size
    # input_size = net.layers[0].size  #input_size is the number of spectral bins in the fft
    window = np.repeat(np.expand_dims(window, axis=1),input_size,axis=1)
    

    sep = np.zeros((int(nchunks*(time_context-overlap)+time_context),input_size))

    
    i=0
    start=0 
    while i < nchunks:
        #import pdb;pdb.set_trace()
        s = fbatch[int(i/batch_size),int(i%batch_size),:,:]

        #print s1.shape
        if start==0:
            sep[0:time_context] = s

        else:
            #print start+overlap
            #print start+time_context
            sep[int(start+overlap):int(start+time_context)] = s[overlap:time_context]
            sep[start:int(start+overlap)] = window[overlap:]*sep[start:int(start+overlap)] + window[:overlap]*s[:overlap]
        i = i + 1 #index for each block
        start = int(start - overlap + time_context) #starting point for each block
    return sep  


def normalize(inputs, feat, mode=config.norm_mode_in):
    if mode == "max_min":
        maximus = np.load(config.stat_dir+feat+'_maximus.npy')
        minimus = np.load(config.stat_dir+feat+'_minimus.npy')
        # import pdb;pdb.set_trace()
        outputs = (inputs-minimus)/(maximus-minimus)

    elif mode == "mean":
        means = np.load(config.stat_dir+feat+'_means.npy')
        stds = np.load(config.stat_dir+feat+'_stds.npy')
        outputs = (inputs-means)/stds
    elif mode == "clip":
        outputs = np.clip(inputs, 0.0,1.0)

    return outputs


def denormalize(inputs, feat, mode=config.norm_mode_in):
    if mode == "max_min":
        maximus = np.load(config.stat_dir+feat+'_maximus.npy')
        minimus = np.load(config.stat_dir+feat+'_minimus.npy')
        # import pdb;pdb.set_trace()
        outputs = (inputs*(maximus-minimus))+minimus

    elif mode == "mean":
        means = np.load(config.stat_dir+feat+'_means.npy')
        stds = np.load(config.stat_dir+feat+'_stds.npy')
        outputs = (inputs*stds)+means
    return outputs

def GenerateRandomData(seed = 2451, dimension = [30, 513]):
    ''' 
        Creates random data with a standard size of 128 * 128
        Generates a float Tensor object with dimensions 1 * 1 * height * width
    '''
    torch.manual_seed(seed)             # seed for replication purposes
    dtype = torch.FloatTensor           # afterwards it can be modified to work with CUDA
    
    rNum = torch.randn(dimension).type(dtype)
    # needs 4 dimensions to work with conv2d (BatchSize, Channels, Height, Width)
    # we add the two extra dimensions at the beginning
    while len(rNum.shape) is not 4:
        rNum = rNum.unsqueeze(0)
    return rNum
    
def main():
    out_feats = input_to_feats(config.wav_dir+'10161_chorus.wav')
    feats_to_audio(out_feats, 'test')
    # test(harmy, 10*np.log10(harm))

    # test_sample = np.random.rand(5170,66)

    # fbatch,i = generate_overlapadd(test_sample)

    # sampled = overlapadd(fbatch,i)

    import pdb;pdb.set_trace()



if __name__ == '__main__':
    main()
