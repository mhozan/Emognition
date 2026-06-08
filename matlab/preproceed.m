function [] = preproceed(varargin)
%PREPROCEED checks for the Test, Calibration or Training mode

S=varargin{1,3};
% assignin('base','Spreproceed',S)
%% get audiofiles and shuffle them
S.audir= S.ed(4).String;  %Audio tokens directory
% S.audiotokens=dir(fullfile([S.audir,'\*.WAV']));  %looking only for .WAV files
%
% hapf=length(dir(fullfile([S.audir,'\*_hap_f.*'])));
% sadf=length(dir(fullfile([S.audir,'\*_sad_f.*'])));
% scaf=length(dir(fullfile([S.audir,'\*_sca_f.*'])));
% angf=length(dir(fullfile([S.audir,'\*_ang_f.*'])));
% neuf=length(dir(fullfile([S.audir,'\*_neu_f.*'])));
% hapm=length(dir(fullfile([S.audir,'\*_hap_m.*'])));
% sadm=length(dir(fullfile([S.audir,'\*_sad_m.*'])));
% scam=length(dir(fullfile([S.audir,'\*_sca_m.*'])));
% angm=length(dir(fullfile([S.audir,'\*_ang_m.*'])));
% neum=length(dir(fullfile([S.audir,'\*_neu_m.*'])));
if S.emo(1).Value
    hapf=(dir(fullfile([S.audir,'\*_hap_f.wav'])));
    hapm=(dir(fullfile([S.audir,'\*_hap_m.wav'])));
else
    hapf=[];hapm=[];
end
if S.emo(2).Value
    scaf=(dir(fullfile([S.audir,'\*_sca_f.wav'])));
    scam=(dir(fullfile([S.audir,'\*_sca_m.wav'])));
else
    scaf=[];scam=[];
end
if S.emo(3).Value
    neuf=(dir(fullfile([S.audir,'\*_neu_f.wav'])));
    neum=(dir(fullfile([S.audir,'\*_neu_m.wav'])));
else
    neuf=[];neum=[];
end
if S.emo(4).Value
    sadf=(dir(fullfile([S.audir,'\*_sad_f.wav'])));
    sadm=(dir(fullfile([S.audir,'\*_sad_m.wav'])));
else
    sadf=[];sadm=[];
end
if S.emo(5).Value
    angf=(dir(fullfile([S.audir,'\*_ang_f.wav'])));
    angm=(dir(fullfile([S.audir,'\*_ang_m.wav'])));
else
    angf=[];angm=[];
end
S.audiotokens=[hapf;hapm;...
    sadf;sadm;...
    scaf;scam;...
    neuf;neum;...
    angf;angm];
S.fems=length(hapf)+length(scaf)+length(sadf)+length(neuf)+length(angf);
S.mals=length(hapm)+length(scam)+length(sadm)+length(neum)+length(angm);
S.wavs=length(S.audiotokens);

% anyvalidnamethere=(hapm||scam||sadm||neum||angm||hapf||scaf||sadf||neuf||angf);


if ~isempty(S.audiotokens) %&& anyvalidnamethere
    inputnamez={S.audiotokens.name}; %get the name field within the structure
    %     if 0
    inputnamez=inputnamez(randperm(length(inputnamez))); %shuffle inputs
    %     end
    S.audiosshuffled={inputnamez};
    
    femindz=regexpi(S.audiosshuffled{1,1},'_f.wav');
    S.femindz=~cellfun(@isempty,femindz)'; %shuffled indices for female inputs
    
    malindz=regexpi(S.audiosshuffled{1,1},'_m.wav');
    S.malindz=~cellfun(@isempty,malindz)'; %shuffled indices for male inputs
    
    % elseif
    
else
    uiwait(errordlg(['No .WAV audio files with valid names in ',S.audir,'\'],'Error 101'))
    set(S.fh,'visible','on')
    return
end



%% get bg image files and shuffle them
S.bgdir=S.ed(5).String;

S.bgimagestruct=[dir(fullfile([S.bgdir,'\*.BMP']));...
    dir(fullfile([S.bgdir,'\*.JPEG']));...
    dir(fullfile([S.bgdir,'\*.JPG']));...
    dir(fullfile([S.bgdir,'\*.PNG']));...
    dir(fullfile([S.bgdir,'\*.GIF']))]; % %;... dir(fullfile([S.bgdir,'\*.GIF']))
%wanna shuffle pictures randomly? use S.picsshuffled in bgchanger


if ~isempty(S.bgimagestruct)   %make sure we have pictures
    xtemp={S.bgimagestruct.name}; %get the name field within the structure
    xtemp=xtemp(randperm(length(xtemp))); %shuffle
    S.picsshuffled={xtemp};
elseif get(S.tt(4),'val') %we are not in calibration mode
    S.picsshuffled={};
else
    uiwait(errordlg(['There are no pictures in ',S.bgdir,'\'],'Error 102'))
    set(S.fh,'visible','on')
    return
end

%%


S.audiodevice=audiodevinfo; %Test audio hardware
if ~isempty(S.audiodevice.output)
    %audio hardware detected, do nothing!
else
    uiwait(errordlg('NO SOUND PLAYBACK DEVICE WAS DETECTED, make sure the hardware is properly installed and an audio driver shows up under Device Manager','Error 103'))
    set(S.fh,'visible','on')
    return
end

if sum(cell2mat(get(S.emo,'value')))>1
    %at least 2 emotions are selected for the test
else  %less than 2 emotions are selected
    uiwait(errordlg('Select at least 2 emotions to proceed.','Error 104'))
    set(S.fh,'visible','on')
    return
end
infoaudio=analyzeaudiodir([],[],S);


S.audinfo=infoaudio;


%% monitor performance
if isfield(S.audinfo,'wav')  %analyzeaudiodir has not returned zero: got confirmation
    
    if  ~get(S.tt(4),'val')%not in calibration
        figsize=[1000 800];
        
        
        
        %         if numel(get(0,'MonitorPositions'))>4   %More than one display? (extended monitors)
        %             pos=[1.1 .1 .4 .6];  %initial position of the monitor window on the second screen
        if S.screen.size(S.screen.maindisplay,3)>1400 && S.screen.size(S.screen.maindisplay,4)>1000
            figsize=[1125 900];
        end
        xinit = S.screen.size(S.screen.maindisplay,1)+ceil(S.screen.size(S.screen.maindisplay,3)/2-figsize(1)/2);% center the figure on the screen horizontally
        yinit = S.screen.size(S.screen.maindisplay,2)+ceil(S.screen.size(S.screen.maindisplay,4)/2-figsize(2)/2); % center the figure on the screen vertically
        
        %         else
        %             %             pos=[.5 .1 .4 .6];
        %             if S.screen.size(1,3)>1800 && S.screen.size(1,4)>1000
        %                 figsize=[1125 875];
        %             end
        %             xinit = ceil(S.screen.size(1,3)/2-figsize(1)/2);% center the figure on the screen horizontally
        %             yinit = ceil(S.screen.size(1,4)/2-figsize(2)/2); % center the figure on the screen vertically
        %
        %         end
        S.fh3 = figure('units','pixels',...'units','normalized',...
            'position',[xinit yinit figsize(1) figsize(2)],... %'position',pos,...
            'menubar','none',...
            'name','Experimenter''s Window',...
            'numbertitle','off',...
            'resize','on','visible','off');
        % tbh = uitoolbar(S.fh3);
        
        S.confuble=axes('units','normalized',...
            'position',[0.6 .5 .4 .4],...
            'XTick',[],'YTick',[]);
        %         'XTickLabel', {'Happy','Scared','Neutral','Sad','Angry'},...
        %         'YTickLabel', {'Happy','Scared','Neutral','Sad','Angry'}
        
        image(S.confuble,rand(5)), colormap(S.confuble,'gray')
        S.confuble.XTick=1:5;
        S.confuble.YTick=1:5;
        S.confuble.XTickLabel = {'Happy','Scared','Neutral','Sad','Angry'};
        S.confuble.XTickLabelRotation=45;
        S.confuble.XAxisLocation='top';
        S.confuble.YTickLabelRotation=45;
        S.confuble.YTickLabel = {'Happy','Scared','Neutral','Sad','Angry'};
        axis(S.confuble,'image')
        %     title('visualization of the confusion matrix')
        
        S.reactimes=axes('units','normalized',...
            'position',[0.09 .05 .46 .35],...
            'tag','react');
        %     plot(1:S.audinfo.wav,ceil(10*rand(1,S.audinfo.wav)))
        title(S.reactimes,'reaction times')
        xlabel(S.reactimes,'Audio#')
        ylabel(S.reactimes,'Reaction(seconds)')
        %         xlim([1 S.audinfo.wav])
        xlim(S.reactimes,[1 120])
        % Create the column and row names in cell arrays
        cnames = {'HAP','SCA','NEU','SAD','ANG'};
        rnames = {'happy','scared','neutral','sad','angry'};
        
        S.tabl=uitable(S.fh3,'Data',zeros(5),...
            'units','normalized',...
            'ColumnWidth',{40},...
            'position',[.61 0.24 .37 .15],...
            'ColumnName',cnames,...
            'RowName',rnames);
        
        S.percentabl=uitable(S.fh3,'Data',zeros(8,3),...
            'units','normalized',...
            'ColumnWidth',{80,100,100},...
            'ColumnFormat', {'bank','bank','bank'},...2 digits
            'position',[.61 0.02 .37 .22],...
            'ColumnName',[{'% Correct'},{'Avg React(S)'},{'Avg Replays'}],...
            'RowName',[rnames,{'female'},{'male'},{'Total'}]);
        
        
        %% general info
        
        if S.tt(1).Value
            stttr='Test Mode';
        elseif S.tt(2).Value && S.tt(3).Value
            stttr='Passive Trainig Mode';
        elseif S.tt(2).Value && ~S.tt(3).Value
            stttr='Active Trainig Mode';
        end
        
        S.axinfo = axes('parent',S.fh3,...
            'units','normalized',...
            'position',[0.08 0.6 .47 .3],...
            'XTick',[],'YTick',[],...
            'XTickLabel',[],'YTickLabel',[],...
            'TickDir','out');
        S.txtinfo(3)=text('parent',S.axinfo,...
            'fontunits','normalized',...
            'units','normalized',...
            'fontsize',.06,...
            'fontw','bold',...
            'color',[.0 0 .2],...
            'position',[.02 .9 0],...
            'horizontalalignment','left',...
            'string',stttr);
        
        text('parent',S.axinfo,...%Version
            'fontunits','normalized',...
            'units','normalized',...
            'fontsize',.06,...
            'fontw','normal',...
            'color',[.3 .3 .3],...
            'position',[.99 .9 0],...
            'horizontalalignment','right',...
            'string',['EMOGNITION ',S.versionn]);
        S.txtinfo(1)=text('parent',S.axinfo,...
            'fontunits','normalized',...
            'units','normalized',...
            'fontsize',.05,...
            'fontw','normal',...
            'color',[.0 0 .2],...
            'position',[.02 .8 0],...
            'horizontalalignment','left',...
            'string',['Subject''s Label:         ',get(S.ed(1),'string')]);
        
        S.txtinfo(2)=text('parent',S.axinfo,...
            'fontunits','normalized',...
            'units','normalized',...
            'fontsize',.05,...
            'fontw','normal',...
            'color',[.0 0 .2],...
            'position',[.02 .7 0],...
            'horizontalalignment','left',...
            'string',['Experimenter:            ',get(S.ed(2),'string')]);
        
        
        if get(S.ch(4),'val')  %monitor performance? make it visible
            set(S.fh3,'visible','on')
        else
            set(S.fh3,'visible','off')
        end
        
    end
    
end





%% Training, Calibration, or The Test
if ~isstruct(infoaudio)  %infoaudio == 0
    disp('Choose another audio directory or update the files in the current one')
else
    
    if S.tt(1).Value %test
        proceed([],[],S)
        
    elseif S.tt(2).Value %training mode
        proceed([],[],S)
        
    elseif S.tt(4).Value% 'calibration'
        calibrationmode([],[],S)
        
    else        %impossible
        
    end
end


if isfield(S,'fh3')
    set(S.fh3,'closerequestfcn',{@rusure,S})
end

% allvars=S;
% S.audinfo=analyzeaudiodir([],[],S);
savesettings(S)


%
% function savesettings(varargin)
% S=varargin{1,3};
% fileID=fopen('prevset.txt','wt');
%
% emo=get(S.emo,'value');
% tt=get(S.tt,'value');
% ed=get(S.ed,'string');
%
% % fprintf(fileID,char(b))
% for i=1:6
% fprintf(fileID,'S.ed(%d).Value %s\n',i,ed{i});
% end
% for i=1:5
% fprintf(fileID,'S.emo(%d).Value %d\n',i,emo{i});
% end
% for i=1:4
% fprintf(fileID,'S.tt(%d).Value %d\n',i,tt{i});
% end
% fclose(fileID);
