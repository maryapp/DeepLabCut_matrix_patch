"""
DeepLabCut2.0 Toolbox (deeplabcut.org)
© A. & M. Mathis Labs
https://github.com/AlexEMG/DeepLabCut
Please see AUTHORS for contributors.

https://github.com/AlexEMG/DeepLabCut/blob/master/AUTHORS
Licensed under GNU Lesser General Public License v3.0

Hao Wu, hwu01@g.harvard.edu contributed the original OpenCV class. Thanks!
You can find the directory for your ffmpeg bindings by: "find / | grep ffmpeg" and then setting it.
"""

####################################################
# Dependencies
####################################################
import os.path
import argparse, os
import numpy as np
from tqdm import trange
from pathlib import Path
import platform

import matplotlib as mpl
if os.environ.get('DLClight', default=False) == 'True':
    mpl.use('AGG') #anti-grain geometry engine #https://matplotlib.org/faq/usage_faq.html
elif platform.system() == 'Darwin':
    mpl.use('WxAgg') #TkAgg
else:
    mpl.use('TkAgg')
import matplotlib.pyplot as plt
from deeplabcut.utils import auxiliaryfunctions, auxfun_multianimal, visualization
from deeplabcut.utils.video_processor import VideoProcessorCV as vp # used to CreateVideo
from matplotlib.animation import FFMpegWriter
from skimage.util import img_as_ubyte
from skimage.draw import circle, line_aa


def get_cmap(n, name='hsv'):
    '''Returns a function that maps each index in 0, 1, ..., n-1 to a distinct
    RGB color; the keyword argument name must be a standard mpl colormap name.'''
    return plt.cm.get_cmap(name, n)

def get_segment_indices(bodyparts2connect, bodyparts2plot):
    bpts2connect = []
    for pair in bodyparts2connect:
        if all(elem in bodyparts2plot for elem in pair):
            bpts2connect.append([bodyparts2plot.index(elem) for elem in pair])
    return bpts2connect


def CreateVideo(clip,Dataframe,pcutoff,dotsize,colormap,bodyparts2plot,
                trailpoints,cropping,x1,x2,y1,y2,
                bodyparts2connect,skeleton_color,draw_skeleton,displaycropped, color_by):
        ''' Creating individual frames with labeled body parts and making a video'''
        if draw_skeleton:
            color_for_skeleton = (np.array(mpl.colors.to_rgba(skeleton_color))[:3]*255).astype(np.uint8)
            #recode the bodyparts2connect into indices for df_x and df_y for speed
            bpts2connect = get_segment_indices(bodyparts2connect, bodyparts2plot)

        if displaycropped:
            ny, nx= y2-y1,x2-x1
        else:
            ny, nx= clip.height(), clip.width()

        fps=clip.fps()
        nframes = len(Dataframe.index)
        duration = nframes/fps

        print("Duration of video [s]: ", round(duration,2), ", recorded with ", round(fps,2),"fps!")
        print("Overall # of frames: ", nframes, "with cropped frame dimensions: ",nx,ny)

        print("Generating frames and creating video.")
        df_x, df_y, df_likelihood = auxiliaryfunctions.form_data_containers(Dataframe, bodyparts2plot)
        if cropping and not displaycropped:
            df_x += x1
            df_y += y1
        colorclass=plt.cm.ScalarMappable(cmap=colormap)
        nbodyparts = len(bodyparts2plot)
        nindividuals = len(df_x) // nbodyparts
        if color_by == 'bodypart':
            C = colorclass.to_rgba(np.linspace(0, 1, nbodyparts))
        else:
            C = colorclass.to_rgba(np.linspace(0, 1, nindividuals))
        colors=(C[:,:3]*255).astype(np.uint8)

        for index in trange(nframes):
            image = clip.load_frame()
            if displaycropped:
                    image=image[y1:y2,x1:x2]

            # Draw the skeleton for specific bodyparts to be connected as specified in the config file
            if draw_skeleton:
                for link in bpts2connect:
                    for ind in range(0, len(df_x), nbodyparts):
                        pair = link[0] + ind, link[1] + ind
                        with np.errstate(invalid='ignore'):
                            if np.all(df_likelihood[pair, index] > pcutoff):
                                rr, cc, val = line_aa(int(np.clip(df_y[pair[0], index], 0, ny - 1)),
                                                      int(np.clip(df_x[pair[0], index], 0, nx - 1)),
                                                      int(np.clip(df_y[pair[1], index], 1, ny - 1)),
                                                      int(np.clip(df_x[pair[1], index], 1, nx - 1)))
                                image[rr, cc] = color_for_skeleton

            for bpindex in range(nbodyparts):
                for ind in range(nindividuals):
                    j = bpindex + ind * nbodyparts
                    if color_by == 'bodypart':
                        color = colors[bpindex]
                    else:
                        color = colors[ind]
                    with np.errstate(invalid='ignore'):
                        if df_likelihood[j, index] > pcutoff:
                            if trailpoints > 0:
                                for k in range(min(trailpoints, index + 1)):
                                    rr, cc = circle(df_y[j, index - k],
                                                    df_x[j, index - k],
                                                    dotsize,
                                                    shape=(ny, nx))
                                    image[rr, cc] = color
                            else:
                                rr, cc = circle(df_y[j, index],
                                                df_x[j, index],
                                                dotsize,
                                                shape=(ny, nx))
                                image[rr, cc] = color

            clip.save_frame(image)
        clip.close()


def CreateVideoSlow(videooutname,clip,Dataframe, tmpfolder, dotsize,colormap,alphavalue,pcutoff,trailpoints,
                    cropping,x1,x2,y1,y2,save_frames,bodyparts2plot,outputframerate,Frames2plot,
                    bodyparts2connect,skeleton_color,draw_skeleton,displaycropped,color_by):
    ''' Creating individual frames with labeled body parts and making a video'''
    #scorer=np.unique(Dataframe.columns.get_level_values(0))[0]
    #bodyparts2plot = list(np.unique(Dataframe.columns.get_level_values(1)))

    if displaycropped:
        ny, nx= y2-y1,x2-x1
    else:
        ny, nx= clip.height(), clip.width()

    fps=clip.fps()
    if  outputframerate is None: #by def. same as input rate.
        outputframerate=clip.fps()

    nframes = len(Dataframe.index)
    duration = nframes/fps

    print("Duration of video [s]: ", round(duration,2), ", recorded with ", round(fps,2),"fps!")
    print("Overall # of frames: ", int(nframes), "with cropped frame dimensions: ",nx,ny)
    print("Generating frames and creating video.")
    df_x, df_y, df_likelihood = auxiliaryfunctions.form_data_containers(Dataframe, bodyparts2plot)
    if cropping and not displaycropped:
        df_x += x1
        df_y += y1
    nbodyparts = len(bodyparts2plot)
    nindividuals = len(df_x) // nbodyparts
    if color_by == 'individual':
        colors = get_cmap(nindividuals, name=colormap)
    else:
        colors = get_cmap(nbodyparts, name=colormap)
    if draw_skeleton:
        #recode the bodyparts2connect into indices for df_x and df_y for speed
        bpts2connect = get_segment_indices(bodyparts2connect, bodyparts2plot)

    nframes_digits=int(np.ceil(np.log10(nframes)))
    if nframes_digits>9:
        raise Exception("Your video has more than 10**9 frames, we recommend chopping it up.")

    if Frames2plot==None:
        Index=range(nframes)
    else:
        Index=[]
        for k in Frames2plot:
            if k>=0 and k<nframes:
                Index.append(int(k))

    # Prepare figure
    prev_backend = plt.get_backend()
    plt.switch_backend('agg')
    dpi = 100
    fig = plt.figure(frameon=False, figsize=(nx / dpi, ny / dpi))
    ax = fig.add_subplot(111)

    writer = FFMpegWriter(fps=fps, codec='h264')
    with writer.saving(fig, videooutname, dpi=dpi):
        for index in trange(nframes):
            imagename = tmpfolder + "/file" + str(index).zfill(nframes_digits) + ".png"
            image = img_as_ubyte(clip.load_frame())
            if index in Index: #then extract the frame!
                if cropping and displaycropped:
                    image = image[y1:y2, x1:x2]
                ax.imshow(image)

                if draw_skeleton:
                    for link in bpts2connect:
                        for ind in range(0, len(df_x), nbodyparts):
                            pair = link[0] + ind, link[1] + ind
                            with np.errstate(invalid='ignore'):
                                if np.all(df_likelihood[pair, index] > pcutoff):
                                    ax.plot([df_x[pair[0], index], df_x[pair[1], index]],
                                            [df_y[pair[0], index], df_y[pair[1], index]],
                                            color=skeleton_color, alpha=alphavalue)

                for bpindex in range(nbodyparts):
                    for ind in range(nindividuals):
                        j = bpindex + ind * nbodyparts
                        if 'part' in color_by:
                            color = colors(bpindex)
                        else:
                            color = colors(ind)
                        with np.errstate(invalid='ignore'):
                            if df_likelihood[j, index] > pcutoff:
                                if trailpoints > 0:
                                    ax.scatter(df_x[j][max(0, index - trailpoints):index],
                                               df_y[j][max(0, index - trailpoints):index],
                                               s=dotsize ** 2,
                                               color=color,
                                               alpha=alphavalue * .75)
                                ax.scatter(df_x[j, index],
                                           df_y[j, index],
                                           s=dotsize ** 2,
                                           color=color,
                                           alpha=alphavalue)
                ax.set_xlim(0, nx)
                ax.set_ylim(0, ny)
                ax.axis('off')
                ax.invert_yaxis()
                fig.subplots_adjust(left=0, bottom=0, right=1, top=1, wspace=0, hspace=0)
                if save_frames:
                    fig.savefig(imagename)
                writer.grab_frame()
                ax.clear()
    print("Labeled video successfully created.")
    plt.switch_backend(prev_backend)


def create_labeled_video(config,videos,videotype='avi',shuffle=1,trainingsetindex=0,
    filtered=False,fastmode=True,save_frames=False,Frames2plot=None, displayedbodyparts='all', displayedindividuals='all',
    codec='mp4v',outputframerate=None, destfolder=None,draw_skeleton=False,
    trailpoints = 0,displaycropped=False, color_by='bodypart',modelprefix=''):
    """
    Labels the bodyparts in a video. Make sure the video is already analyzed by the function 'analyze_video'

    Parameters
    ----------
    config : string
        Full path of the config.yaml file as a string.

    videos : list
        A list of strings containing the full paths to videos for analysis or a path to the directory, where all the videos with same extension are stored.

    videotype: string, optional
        Checks for the extension of the video in case the input to the video is a directory.\n Only videos with this extension are analyzed. The default is ``.avi``

    shuffle : int, optional
        Number of shuffles of training dataset. Default is set to 1.

    trainingsetindex: int, optional
        Integer specifying which TrainingsetFraction to use. By default the first (note that TrainingFraction is a list in config.yaml).

    filtered: bool, default false
        Boolean variable indicating if filtered output should be plotted rather than frame-by-frame predictions. Filtered version can be calculated with deeplabcut.filterpredictions

    videotype: string, optional
        Checks for the extension of the video in case the input is a directory.\nOnly videos with this extension are analyzed. The default is ``.avi``

    fastmode: bool
        If true uses openCV (much faster but less customization of video) vs matplotlib (if false). You can also
        "save_frames" individually or not in the matplotlib mode (if you set the "save_frames" variable accordingly).
        However, using matplotlib to create the frames it therefore allows much more flexible (one can set transparency of markers, crop, and easily customize).

    save_frames: bool
        If true creates each frame individual and then combines into a video. This variant is relatively slow as
        it stores all individual frames.

    Frames2plot: List of indices
        If not None & save_frames=True then the frames corresponding to the index will be plotted. For example, Frames2plot=[0,11] will plot the first and the 12th frame.

    displayedbodyparts: list of strings, optional
        This selects the body parts that are plotted in the video. Either ``all``, then all body parts
        from config.yaml are used orr a list of strings that are a subset of the full list.
        E.g. ['hand','Joystick'] for the demo Reaching-Mackenzie-2018-08-30/config.yaml to select only these two body parts.

    displayedindividuals: list of strings, optional
        Individuals plotted in the video. By default, all individuals present in the config will be showed.

    codec: codec for labeled video. Options see http://www.fourcc.org/codecs.php [depends on your ffmpeg installation.]

    outputframerate: positive number, output frame rate for labeled video (only available for the mode with saving frames.) By default: None, which results in the original video rate.

    destfolder: string, optional
        Specifies the destination folder that was used for storing analysis data (default is the path of the video).

    draw_skeleton: bool
        If ``True`` adds a line connecting the body parts making a skeleton on on each frame. The body parts to be connected and the color of these connecting lines are specified in the config file. By default: ``False``

    trailpoints: int
        Number of revious frames whose body parts are plotted in a frame (for displaying history). Default is set to 0.

    displaycropped: bool, optional
        Specifies whether only cropped frame is displayed (with labels analyzed therein), or the original frame with the labels analyzed in the cropped subset.

    color_by : string, optional (default='bodypart')
        Coloring rule. By default, each bodypart is colored differently.
        If set to 'individual', points belonging to a single individual are colored the same.

    Examples
    --------
    If you want to create the labeled video for only 1 video
    >>> deeplabcut.create_labeled_video('/analysis/project/reaching-task/config.yaml',['/analysis/project/videos/reachingvideo1.avi'])
    --------

    If you want to create the labeled video for only 1 video and store the individual frames
    >>> deeplabcut.create_labeled_video('/analysis/project/reaching-task/config.yaml',['/analysis/project/videos/reachingvideo1.avi'],fastmode=True, save_frames=True)
    --------

    If you want to create the labeled video for multiple videos
    >>> deeplabcut.create_labeled_video('/analysis/project/reaching-task/config.yaml',['/analysis/project/videos/reachingvideo1.avi','/analysis/project/videos/reachingvideo2.avi'])
    --------

    If you want to create the labeled video for all the videos (as .avi extension) in a directory.
    >>> deeplabcut.create_labeled_video('/analysis/project/reaching-task/config.yaml',['/analysis/project/videos/'])

    --------
    If you want to create the labeled video for all the videos (as .mp4 extension) in a directory.
    >>> deeplabcut.create_labeled_video('/analysis/project/reaching-task/config.yaml',['/analysis/project/videos/'],videotype='mp4')

    --------

    """
    cfg = auxiliaryfunctions.read_config(config)
    trainFraction = cfg['TrainingFraction'][trainingsetindex]
    DLCscorer,DLCscorerlegacy = auxiliaryfunctions.GetScorerName(cfg,shuffle,trainFraction,modelprefix=modelprefix) #automatically loads corresponding model (even training iteration based on snapshot index)

    if save_frames:
        fastmode=False #otherwise one cannot save frames

    bodyparts=auxiliaryfunctions.IntersectionofBodyPartsandOnesGivenbyUser(cfg,displayedbodyparts)
    individuals = auxfun_multianimal.IntersectionofIndividualsandOnesGivenbyUser(cfg, displayedindividuals)
    if draw_skeleton:
        bodyparts2connect = cfg['skeleton']
        skeleton_color = cfg['skeleton_color']
    else:
        bodyparts2connect = None
        skeleton_color = None

    start_path=os.getcwd()
    Videos=auxiliaryfunctions.Getlistofvideos(videos,videotype)
    if not len(Videos):
        print("No video(s) were found. Please check your paths and/or 'video_type'.")
        return

    for video in Videos:
        if destfolder is None:
            videofolder= Path(video).parents[0] #where your folder with videos is.
        else:
            videofolder=destfolder

        os.chdir(str(videofolder))
        videotype = Path(video).suffix
        print("Starting % ", videofolder, videos)
        vname = str(Path(video).stem)

        #if notanalyzed:
        #notanalyzed,outdataname,sourcedataname,DLCscorer=auxiliaryfunctions.CheckifPostProcessing(folder,vname,DLCscorer,DLCscorerlegacy,suffix='checking')

        if filtered==True:
            videooutname1=os.path.join(vname + DLCscorer+'filtered_labeled.mp4')
            videooutname2=os.path.join(vname + DLCscorerlegacy+'filtered_labeled.mp4')
        else:
            videooutname1=os.path.join(vname + DLCscorer+'_labeled.mp4')
            videooutname2=os.path.join(vname + DLCscorerlegacy+'_labeled.mp4')

        if os.path.isfile(videooutname1) or os.path.isfile(videooutname2):
            print("Labeled video already created.")
        else:
            print("Loading ", video, "and data.")
            datafound,metadata,Dataframe,DLCscorer,suffix=auxiliaryfunctions.LoadAnalyzedData(str(videofolder),vname,DLCscorer,filtered) #returns boolean variable if data was found and metadata + pandas array
            s = '_idv' if color_by == 'individual' else '_bp'
            videooutname = os.path.join(vname + DLCscorer + suffix + s + '_labeled.mp4')
            if datafound:  # Sweet, we've found single animal data or tracklets
                if os.path.isfile(videooutname):
                    print('Labeled video already created. Skipping...')
                    continue

                if all(individuals):
                    Dataframe = Dataframe.loc(axis=1)[:, individuals]

                cropping=metadata['data']["cropping"]
                [x1,x2,y1,y2]=metadata['data']["cropping_parameters"]
                labeled_bpts = [bp for bp in bodyparts if bp in Dataframe.columns.get_level_values('bodyparts')]
                if not fastmode:
                    tmpfolder = os.path.join(str(videofolder),'temp-' + vname)
                    if save_frames:
                        auxiliaryfunctions.attempttomakefolder(tmpfolder)
                    clip = vp(video)
                    CreateVideoSlow(videooutname,clip,Dataframe,tmpfolder,cfg["dotsize"],cfg["colormap"],cfg["alphavalue"],cfg["pcutoff"],
                                    trailpoints,cropping,x1,x2,y1,y2,save_frames,labeled_bpts,outputframerate,Frames2plot,bodyparts2connect,
                                    skeleton_color,draw_skeleton,displaycropped,color_by)
                else:
                    if displaycropped: #then the cropped video + the labels is depicted
                        clip = vp(fname = video,sname = videooutname,codec=codec,sw=x2-x1,sh=y2-y1)
                    else: #then the full video + the (perhaps in cropped mode analyzed labels) are depicted
                        clip = vp(fname = video,sname = videooutname,codec=codec)
                    CreateVideo(clip,Dataframe,cfg["pcutoff"],cfg["dotsize"],cfg["colormap"],labeled_bpts,trailpoints,cropping,x1,x2,y1,y2,bodyparts2connect,skeleton_color,draw_skeleton,displaycropped,color_by)
            else:
                # Check if tracks exist!
                datafound, metadata, Tracks, DLCscorer = auxiliaryfunctions.LoadAnalyzedDetectionData(videofolder, vname, DLCscorer)
                if not datafound:
                    print('No data were found. Run "analyze_video" first.')
                    if cfg.get('multianimalproject', False):
                        print('Then use "convert_detections2tracklets" and re-run the current function.')
                    continue
                else:
                    print('Raw detections were found. Although "convert_detections2tracklets" '
                          'should be used first, the video will be created anyway.')
                    ## TODO: integrate with standard code for dataframes.
                    scale=1
                    pcutoff=cfg["pcutoff"]
                    _create_video_from_tracks(video, Tracks, vname, videooutname, pcutoff, scale)

    os.chdir(start_path)


def create_video_with_all_detections(config, videos, DLCscorername, destfolder=None):
    """
    Create a video labeled with all the detections stored in a '*_full.pickle' file.

    Parameters
    ----------
    config : str
        Absolute path to the config.yaml file

    videos : list of str
        A list of strings containing the full paths to videos for analysis or a path to the directory,
        where all the videos with same extension are stored.

    DLCscorername: str
        Name of network. E.g. 'DLC_resnet50_project_userMar23shuffle1_50000

    destfolder: string, optional
        Specifies the destination folder that was used for storing analysis data (default is the path of the video).

    """
    from deeplabcut.pose_estimation_tensorflow.lib.inferenceutils import convertdetectiondict2listoflist
    import pickle, re
    cfg = auxiliaryfunctions.read_config(config)

    for video in videos:
        if destfolder is None:
            outputname = '{}_full.mp4'.format(os.path.splitext(video)[0]+DLCscorername)
            full_pickle=os.path.join(os.path.splitext(video)[0]+DLCscorername+'_full.pickle')
        else:
            outputname = os.path.join(destfolder,str(Path(video).stem)+DLCscorername+'_full.mp4')
            full_pickle=os.path.join(destfolder,str(Path(video).stem)+DLCscorername+'_full.pickle')

        if not(os.path.isfile(outputname)):
            print("Creating labeled video for ", str(Path(video).stem))
            with open(full_pickle, 'rb') as file:
                data = pickle.load(file)

            header = data.pop('metadata')
            print(header)
            all_jointnames = header['all_joints_names']

            numjoints = len(all_jointnames)
            bpts = range(numjoints)
            frame_names = list(data)
            frames = [int(re.findall(r'\d+', name)[0]) for name in frame_names]
            colorclass = plt.cm.ScalarMappable(cmap=cfg['colormap'])
            C = colorclass.to_rgba(np.linspace(0, 1, numjoints))
            colors = (C[:, :3] * 255).astype(np.uint8)

            pcutoff = cfg['pcutoff']
            dotsize = cfg['dotsize']
            clip = vp(fname=video, sname=outputname, codec='mp4v')
            ny, nx = clip.height(), clip.width()

            for n in trange(clip.nframes):
                frame = clip.load_frame()
                try:
                    ind = frames.index(n)
                    dets = convertdetectiondict2listoflist(data[frame_names[ind]], bpts)
                    for i, det in enumerate(dets):
                        color = colors[i]
                        for x, y, p, _ in det:
                            if p > pcutoff:
                                rr, cc = circle(y, x, dotsize, shape=(ny, nx))
                                frame[rr, cc] = color
                except ValueError:  # No data stored for that particular frame
                    print(n,'no data')
                    pass
                try:
                    clip.save_frame(frame)
                except:
                    print(n,"frame writing error.")
                    pass
            clip.close()
        else:
            print("Detections already plotted, ", outputname)


def _create_video_from_tracks(video, tracks, destfolder, output_name, pcutoff, scale=1):
    import cv2
    import subprocess
    from tqdm import tqdm

    if not os.path.isdir(destfolder):
        os.mkdir(destfolder)

    cap = cv2.VideoCapture(video)
    nframes = int(cap.get(7))
    strwidth = int(np.ceil(np.log10(nframes)))  # width for strings
    ny = int(cap.get(4))
    nx = int(cap.get(3))
    # cropping!
    X2 = nx  # 1600
    X1 = 0
    # nx=X2-X1
    numtracks = len(tracks.keys()) - 1
    trackids = [t for t in tracks.keys() if t != 'header']
    cc = np.random.rand(numtracks + 1, 3)
    fig, ax = visualization.prepare_figure_axes(nx, ny, scale)
    im = ax.imshow(np.zeros((ny, nx)))
    markers = sum([ax.plot([], [], '.', c=c) for c in cc], [])
    for index in tqdm(range(nframes)):
        cap.set(1, index)
        ret, frame = cap.read()
        imname = 'frame' + str(index).zfill(strwidth)
        image_output = os.path.join(destfolder, imname + '.png')
        if ret and not os.path.isfile(image_output):
            frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            im.set_data(frame[:, X1:X2])
            for n, trackid in enumerate(trackids):
                if imname in tracks[trackid]:
                    x, y, p = tracks[trackid][imname].reshape((-1, 3)).T
                    markers[n].set_data(x[p > pcutoff], y[p > pcutoff])
                else:
                    markers[n].set_data([], [])
            fig.subplots_adjust(left=0, bottom=0, right=1, top=1, wspace=0, hspace=0)
            plt.savefig(image_output)

    outputframerate = 30
    os.chdir(destfolder)

    subprocess.call([
        'ffmpeg', '-framerate', str(int(cap.get(5))), '-i', f'frame%0{strwidth}d.png',
        '-r', str(outputframerate), output_name])


def create_video_from_pickled_tracks(video, pickle_file, destfolder='', output_name='', pcutoff=0.6):
    if not destfolder:
        destfolder = os.path.splitext(video)[0]
    if not output_name:
        video_name, ext = os.path.splitext(os.path.split(video)[1])
        output_name = video_name + 'DLClabeled' + ext
    tracks = auxiliaryfunctions.read_pickle(pickle_file)
    _create_video_from_tracks(video, tracks, destfolder, output_name, pcutoff)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('config')
    parser.add_argument('videos')
    cli_args = parser.parse_args()
