import numpy as np
import torch
from torch.autograd import Variable
import torch.nn as nn
from collections import OrderedDict
from data_pipeline import data_gen
import matplotlib.pyplot as plt
import config
import utils
import datetime
import sys
import time


class AutoEncoder(nn.Module):
    def __init__(self, conv_hor_in = (1, 513), conv_ver_in = (12, 1)):
        '''
        I tried to make this as customizable as possible.
        INPUT:
                -   conv_hor_in: size of the kernel filter for the horizontal convolution.
                                 Must be a tuple.
                                                        (Height, Width)
                    
                -   conv_hor_in: same as the conv_hor_in but for the vertical convolution.
                                 Must be a tuple.
                                                        (Height, Width)
                    
                -   out_channels_in: number of channels of features we want the network to create 
                                   on each convolution
        '''
    
        super(AutoEncoder, self).__init__() # reference current class in each instance
        
        # init conv/deconv filter shapes
        self.conv_hor = conv_hor_in
        self.conv_ver = conv_ver_in

        ### ENCODER
        # init autoencoder architecture shape
        # we need to use sequential, as it's a way to add modules one after the 
        # another in an ordered way
        self.encoder = nn.Sequential(
            nn.Conv2d(2, 2, self.conv_hor, stride = 1, padding = 0, bias = True),
            nn.Conv2d(2, 2, self.conv_ver, stride = 1, padding = 0, bias = True)
        )
        
        ### DECODERS
        self.decode_drums = nn.Sequential(
            nn.ConvTranspose2d(2, 2, self.conv_ver, stride = 1, padding = 0, bias = True),
            nn.ReLU(),
            nn.ConvTranspose2d(2, 2, self.conv_hor, stride = 1, padding = 0, bias = True),
            nn.ReLU()
        )
        self.decode_voice = nn.Sequential(
            nn.ConvTranspose2d(2, 2, self.conv_ver, stride = 1, padding = 0, bias = True),
            nn.ReLU(),
            nn.ConvTranspose2d(2, 2, self.conv_hor, stride = 1, padding = 0, bias = True),
            nn.ReLU()
        )
        self.decode_bass = nn.Sequential(
            nn.ConvTranspose2d(2, 2, self.conv_ver, stride = 1, padding = 0, bias = True),
            nn.ReLU(),
            nn.ConvTranspose2d(2, 2, self.conv_hor, stride = 1, padding = 0, bias = True),
            nn.ReLU()
        )
        self.decode_other = nn.Sequential(
            nn.ConvTranspose2d(2, 2, self.conv_ver, stride = 1, padding = 0, bias = True),
            nn.ReLU(),
            nn.ConvTranspose2d(2, 2, self.conv_hor, stride = 1, padding = 0, bias = True),
            nn.ReLU()
        )
        
        ### FULLY CONNECTED LAYERS
        self.layer_first = nn.Linear(38, 128)

        self.layer_drums = nn.Sequential(
            nn.Linear(128, 38),
            nn.ReLU()
        )
        self.layer_voice = nn.Sequential(
            nn.Linear(128, 38),
            nn.ReLU()
        )
        self.layer_bass = nn.Sequential(
            nn.Linear(128, 38),
            nn.ReLU()
        )
        self.layer_other = nn.Sequential(
            nn.Linear(128, 38),
            nn.ReLU()
        )
        
        # put the layers and deconv in libraries to make it easier to work with
        self.layers = OrderedDict([
            ("voice", self.layer_voice),
            ("drums", self.layer_drums),
            ("bass",  self.layer_bass),
            ("other", self.layer_other)
            ])
            
        self.deconvs = OrderedDict([
            ("voice", self.decode_voice),
            ("drums", self.decode_drums),
            ("bass",  self.decode_bass),
            ("other", self.decode_other)
            ])
                
        # OUTPUT MATRIX
        # Create a tensor variable with shape (15, 1, 30, 513)
        # care, as the channels dimension is initialized with 1, and we are appending to it
        self.final_output = Variable()

        
    def forward(self, x):  
          
        encode = self.encoder(x)

        encode = encode.view(15, -1)

        layer_output = self.layer_first(encode)
        
        output_flag = 0
        
        for key in self.layers:
            
            source_output = self.layers[key](layer_output)

            source_deconv = self.deconvs[key](source_output.view(-1,2,19,1))

            if  output_flag == 0:
                self.final_output = source_deconv
                output_flag = 1
            else:
                self.final_output = torch.cat((source_deconv, self.final_output), dim = 1)
                
        return self.final_output



    
def trainNetwork(save_name = 'model_e' + str(config.num_epochs) + '_b' + str(config.batches_per_epoch_train) + '_bs' + str(config.batch_size) ):
    assert torch.cuda.is_available(), "Code only usable with cuda"

    #autoencoder =  AutoEncoder().cuda()

    autoencoder =  AutoEncoder().cuda()

    optimizer   =  torch.optim.Adagrad(autoencoder.parameters(), 0.0001 )

    #loss_func   =  nn.MSELoss( size_average=False )
    loss_func   =  nn.L1Loss( size_average=False )

    train_evol = []

    count = 0

    alpha = 0.001
    beta  = 0.01
    beta_voc = 0.03

    for epoch in range(config.num_epochs):

        start_time = time.time()

        generator = data_gen()

        train_loss = 0

        optimizer.zero_grad()

        count = 0

        for inputs, targets in generator:
            targets = targets *np.linspace(1.0,0.7,513)

            targets_cuda = Variable(torch.FloatTensor(targets)).cuda()
            inputs = Variable(torch.FloatTensor(inputs)).cuda()


            output = autoencoder(inputs)

            mask_vocals = output[:,:2,:,:]

            mask_drums = output[:,2:4,:,:]

            mask_bass = output[:,4:6,:,:]

            mask_others = output[:,6:,:,:]

            out_vocals = inputs * mask_vocals

            out_drums = inputs * mask_drums

            out_bass = inputs * mask_bass

            out_others = inputs * mask_others

            targets_vocals = targets_cuda[:,:2,:,:]

            targets_drums = targets_cuda[:,2:4,:,:]

            targets_bass = targets_cuda[:,4:6,:,:]

            targets_others = targets_cuda[:,6:,:,:]

            step_loss_vocals = loss_func(out_vocals, targets_vocals)
            alpha_diff =  alpha * loss_func(out_vocals, targets_bass)
            alpha_diff += alpha * loss_func(out_vocals, targets_drums)
            beta_other_voc   =  beta_voc * loss_func(out_vocals, targets_others)

            step_loss_drums = loss_func(out_drums, targets_drums)
            alpha_diff +=  alpha *  loss_func(out_drums, targets_vocals)
            alpha_diff +=  alpha *  loss_func(out_drums, targets_bass)
            beta_other  =  beta  *  loss_func(out_drums, targets_others)

            step_loss_bass = loss_func(out_bass, targets_bass)
            alpha_diff +=  alpha *  loss_func(out_bass, targets_vocals)
            alpha_diff +=  alpha *  loss_func(out_bass, targets_drums)
            beta_other  =  beta  *  loss_func(out_bass, targets_others)

            # add regularization terms from paper
            step_loss = abs(step_loss_vocals + step_loss_drums + step_loss_bass - beta_other - alpha_diff - beta_other_voc)

            train_loss += step_loss.item()

            step_loss.backward()

            optimizer.step()

            utils.progress(count,config.batches_per_epoch_train, suffix = 'training done')

            count+=1

        train_evol.append([step_loss_vocals/count,step_loss_drums/count, step_loss_bass/count, loss_func(out_others, targets_others)/count, train_loss/count])
        duration = time.time()-start_time

        if (epoch+1)%config.print_every == 0:
            print('epoch %d/%d, took %0.00f seconds, epoch total loss: %0.0f' % (epoch+1, config.num_epochs, duration, train_loss))
        if (epoch+1)%config.save_every  == 0:
            torch.save(autoencoder.state_dict(), config.log_dir+save_name+'_'+str(epoch)+'.pt')
            np.save(config.log_dir+'train_loss',train_evol)

    torch.save(autoencoder.state_dict(), config.log_dir+save_name+'_'+str(epoch)+'.pt')


def evalNetwork(file_name, load_name='model', plot = False):
    autoencoder_audio = AutoEncoder().cuda()
    epoch = 50
    autoencoder_audio.load_state_dict(torch.load(config.log_dir+load_name+'_'+str(epoch)+'.pt'))


    audio,fs = stempeg.read_stems(os.path.join(config.wav_dir_train,file_name), stem_id=[0,1,2,3,4])

    mixture = audio[0]

    drums = audio[1]

    bass = audio[2]

    acc = audio[3]

    vocals = audio[4]

    mix_stft, mix_phase = utils.stft_stereo(mixture,phase=True)

    drums_stft = utils.stft_stereo(drums)

    bass_stft = utils.stft_stereo(bass)

    acc_stft = utils.stft_stereo(acc)

    voc_stft = utils.stft_stereo(vocals)

    in_batches, nchunks_in = utils.generate_overlapadd(mix_stft)

    out_batches = []

    for in_batch in in_batches:
        # import pdb;pdb.set_trace()
        in_batch = Variable(torch.FloatTensor(in_batch)).cuda()
        out_batch = autoencoder_audio(in_batch)
        out_batches.append(np.array(out_batch.data.cpu().numpy()))
        

    out_batches = np.array(out_batches)
    

    out_vocals = out_batches[:,:,:2,:,:]

    out_drums = out_batches[:,:,2:4,:,:]

    out_bass = out_batches[:,:,4:6,:,:]

    out_others = out_batches[:,:,6:,:,:]
    
    out_drums = utils.overlapadd(out_drums, nchunks_in) 

    out_bass = utils.overlapadd(out_bass, nchunks_in) 

    out_others = utils.overlapadd(out_others, nchunks_in) 

    out_vocals = utils.overlapadd(out_vocals, nchunks_in) 

    if plot:
        plt.figure(1)
        plt.suptitle(file_name[:-9])
        ax1 = plt.subplot(411)
        plt.imshow(np.log(drums_stft[0].T),aspect = 'auto', origin = 'lower')
        ax1.set_title("Drums Left Channel Ground Truth", fontsize = 10)
        ax2 = plt.subplot(412)
        plt.imshow(np.log(out_drums[0].T),aspect = 'auto', origin = 'lower')
        ax2.set_title("Drums Left Channel Network Output", fontsize = 10)
        ax3 = plt.subplot(413)
        plt.imshow(np.log(drums_stft[1].T),aspect = 'auto', origin = 'lower')
        ax3.set_title("Drums Right Channel Ground Truth", fontsize = 10)
        ax4 = plt.subplot(414)
        plt.imshow(np.log(out_drums[1].T),aspect = 'auto', origin = 'lower')
        ax4.set_title("Drums Right Channel Network Output", fontsize = 10)
        plt.show()

def plot_loss():
    train_loss = np.load(config.log_dir+'train_loss.npy')
    plt.plot(train_loss)
    plt.show()
        
if __name__ == '__main__':
    if sys.argv[1] == '-train' or sys.argv[1] == '--train' or sys.argv[1] == '--t' or sys.argv[1] == '-t':
        print("Training")
        trainNetwork()
    elif sys.argv[1] == '-synth' or sys.argv[1] == '--synth' or sys.argv[1] == '--s' or sys.argv[1] == '-s':
        if len(sys.argv)<3:
            print("Please give a file to synthesize")
        else:
            file_name = sys.argv[2]
            if not file_name.endswith('.stem.mp4'):
                file_name = file_name+'.stem.mp4'

            print("Synthesizing File %s"% file_name)
            if '-p' in sys.argv or '--p' in sys.argv or '-plot' in sys.argv or '--plot' in sys.argv:                

                print("Just showing plots for File %s"% sys.argv[2])
                evalNetwork(file_name,plot=True)
    elif sys.argv[1] == '-plot' or sys.argv[1] == '--pl' or sys.argv[1] == '--plot_loss':
        plot_loss()
            # else:
            #     print("Synthesizing File %s, Not Showing Plots"% sys.argv[2])
            #     synth_file(file_name,show_plots=False, save_file=True)

    elif sys.argv[1] == '-help' or sys.argv[1] == '--help' or sys.argv[1] == '--h' or sys.argv[1] == '-h':
        print("%s --train to train the model"%sys.argv[0])
        print("%s --synth <filename> to synthesize file"%sys.argv[0])
        print("%s --synth <filename> -- plot to synthesize file and show plots"%sys.argv[0])
        print("%s --synth <filename> -- plot --ns to just show plots"%sys.argv[0])
    else:
        print("Unable to decipher inputs please use %s --help for help on how to use this function"%sys.argv[0])
