import numpy as np
import os
import time
import h5py

import config

def data_gen(in_dir=config.dir_hdf5):

    sources = ['voc_stft', 'drums_stft', 'bass_stft', 'acc_stft']
    
    file_list = [x for x in os.listdir(in_dir) if x.endswith('.hdf5') and not x.startswith('._')]

    max_files_to_process = int(config.batch_size/config.samples_per_file)


    num_files = len(file_list)

    for k in range(config.batches_per_epoch_train):

        inputs = []
        targets = []

        #start_time = time.time()

        for i in range(max_files_to_process):
            
            p = np.random.random_sample()
            
            # Randomize which batches are augmentated
            if config.data_aug is True and p < 0.2:
                #print ('random')
                # each sample is a different file
                for j in range(config.samples_per_file):
                    
                    # Random file for each source
                    file_index = [np.random.randint(0,num_files) for x in range(4)]
                    
                    source_i = 0
                    
                    mix_stft = []
                    mix_stft = np.ndarray(mix_stft)
                    
                    sources_stft = []
                    
                    for source in sources:
                        file_to_open = file_list[file_index[source_i]]
                        
                        hdf5_file = h5py.File(in_dir+file_to_open, "r")
                        
                        source_stft = hdf5_file[source]
                        file_len = source_stft.shape[1]
                        
                        # random stft time index
                        index=np.random.randint(0,file_len-config.max_phr_len)
                        
                        source_stft = source_stft[:,index:index+config.max_phr_len,:]
                        
                        if source_i == 0:
                            sources_stft = source_stft
                            
                            # this might be wrong, but I think it still makes sense:
                            mix_stft = source_stft/4
                            
                        else:
                            sources_stft = np.concatenate((sources_stft, source_stft),axis=0)
                            
                            mix_stft += source_stft/4
                            
                        source_i += 1
                        
                    targets.append(sources_stft)
                    inputs.append(mix_stft)

            else:
                file_index = np.random.randint(0,num_files)
                file_to_open = file_list[file_index]

                hdf5_file = h5py.File(in_dir+file_to_open, "r")

                voc_stft = hdf5_file['voc_stft']

                mix_stft = hdf5_file['mix_stft']

                drums_stft = hdf5_file['drums_stft']

                bass_stft = hdf5_file['bass_stft']

                acc_stft = hdf5_file['acc_stft']

                file_len = voc_stft.shape[1]
                
                for j in range(config.samples_per_file):
                        index=np.random.randint(0,file_len-config.max_phr_len)
                        targets.append(np.concatenate((voc_stft[:,index:index+config.max_phr_len,:],\
                                                       drums_stft[:,index:index+config.max_phr_len,:],\
                                                       bass_stft[:,index:index+config.max_phr_len,:],\
                                                       acc_stft[:,index:index+config.max_phr_len,:]),axis=0))
                        inputs.append(mix_stft[:,index:index+config.max_phr_len,:])
                
               
                
        #print(time.time()-start_time)
        yield np.array(inputs), np.array(targets)
    
    #import pdb;pdb.set_trace()


    
def main():
    # get_stats(feat='feats')
    gen = data_gen()
    for inp, tar in gen:
        z = inp
    # vg = val_generator()
    # gen = get_batches()


    #import pdb;pdb.set_trace()


if __name__ == '__main__':
    main()
