function [yyy] = analyzeaudiodir(varargin)
%ANALYZEAUDIODIR examines all the wav files in the audio directory
%gets only called by preproceed.m
% x=varargin;
% yyy=assignin('base','pb1image',varargin);
S=varargin{1,3};
% assignin('base','Sanalyze',S);
% filenames={S.audiotokens.name};
filenames_shuffled=S.audiosshuffled{1,1};
allnamesstring=strjoin(filenames_shuffled,'; \n'); %combine all the file names into a single string
% wav_Indices=regexpi(allnamesstring,'.wav');  %case insensetive
% S.audinfo.wav=length(wav_Indices);
S.audinfo.wav=S.wavs;
% wav_Indices=strfind(allnamesstring,'.wav'); case sensitive
% female_Indices=regexpi(allnamesstring,'_f.');
% S.audinfo.f=length(female_Indices);
S.audinfo.f=S.fems;
% male_Indices=regexpi(allnamesstring,'_m.');
% S.audinfo.m=length(male_Indices);
S.audinfo.m=S.mals;

[~, S.audinfo.audiofoldername, ~] = fileparts(S.audir);
S.audinfo.audiofoldername=['_',S.audinfo.audiofoldername];
hap_Indices=regexpi(allnamesstring,'_hap_');
hap_f_Indices=regexpi(allnamesstring,'_hap_f.');
hap_m_Indices=regexpi(allnamesstring,'_hap_m.');
% S.audinfo.hap.all=length(hap_Indices);
S.audinfo.hap.f=length(hap_f_Indices);
S.audinfo.hap.m=length(hap_m_Indices);
S.audinfo.hap.all=S.audinfo.hap.f+S.audinfo.hap.m;

sca_Indices=regexpi(allnamesstring,'_sca_');
sca_f_Indices=regexpi(allnamesstring,'_sca_f.');
sca_m_Indices=regexpi(allnamesstring,'_sca_m.');
% S.audinfo.sca.all=length(sca_Indices);
S.audinfo.sca.f=length(sca_f_Indices);
S.audinfo.sca.m=length(sca_m_Indices);
S.audinfo.sca.all=S.audinfo.sca.f+S.audinfo.sca.m;

neu_Indices=regexpi(allnamesstring,'_neu_');
neu_f_Indices=regexpi(allnamesstring,'_neu_f.');
neu_m_Indices=regexpi(allnamesstring,'_neu_m.');
% S.audinfo.neu.all=length(neu_Indices);
S.audinfo.neu.f=length(neu_f_Indices);
S.audinfo.neu.m=length(neu_m_Indices);
S.audinfo.neu.all=S.audinfo.neu.f+S.audinfo.neu.m;

sad_Indices=regexpi(allnamesstring,'_sad_');
sad_f_Indices=regexpi(allnamesstring,'_sad_f.');
sad_m_Indices=regexpi(allnamesstring,'_sad_m.');
S.audinfo.sad.f=length(sad_f_Indices);
S.audinfo.sad.m=length(sad_m_Indices);
% S.audinfo.sad.all=length(sad_Indices);
S.audinfo.sad.all=S.audinfo.sad.f+S.audinfo.sad.m;

ang_Indices=regexpi(allnamesstring,'_ang_');
ang_f_Indices=regexpi(allnamesstring,'_ang_f.');
ang_m_Indices=regexpi(allnamesstring,'_ang_m.');
% S.audinfo.ang.all=length(ang_Indices);
S.audinfo.ang.f=length(ang_f_Indices);
S.audinfo.ang.m=length(ang_m_Indices);
S.audinfo.ang.all=S.audinfo.ang.f+S.audinfo.ang.m;


emoind=[hap_Indices,sca_Indices,neu_Indices,sad_Indices,ang_Indices].';
emotags=[1*ones(size(hap_Indices)),...
    2*ones(size(sca_Indices)),...
    3*ones(size(neu_Indices)),...
    4*ones(size(sad_Indices)),...
    5*ones(size(ang_Indices))].';
S.audinfo.emoindices=[emoind,emotags];
xx=S.audinfo.emoindices;
[~, index1] = sort(xx(:,1));  %sort both columns  by column 1 order
xx=xx(index1,:); %sorting
S.audinfo.emoindsorted = xx(:,2); %picking the 2nd column; this must be compared with the pressed keys bu user
S.audinfo.hapindsorted=find(S.audinfo.emoindsorted==1); %happy sequences, sorted
S.audinfo.scaindsorted=find(S.audinfo.emoindsorted==2);
S.audinfo.neuindsorted=find(S.audinfo.emoindsorted==3);
S.audinfo.sadindsorted=find(S.audinfo.emoindsorted==4);
S.audinfo.angindsorted=find(S.audinfo.emoindsorted==5);

% S.audinfo.correct= false(S.audinfo.wav,1);   %%empty logical array to store right and wrong answers


str1=sprintf('\n\nValid *.wav files:	 %i\n',S.audinfo.wav);
strf=sprintf('Female voices:	   %i\n',S.audinfo.f);
strm=sprintf('Male voices:   	    %i\n',S.audinfo.m);
strsad=sprintf('sad:        %i  (%i f, %i m)\n',S.audinfo.sad.all,S.audinfo.sad.f,S.audinfo.sad.m);
strang=sprintf('ang:        %i  (%i f, %i m)\n\n',S.audinfo.ang.all,S.audinfo.ang.f,S.audinfo.ang.m);
strneu=sprintf('neu:        %i  (%i f, %i m)\n',S.audinfo.neu.all,S.audinfo.neu.f,S.audinfo.neu.m);
strhap=sprintf('hap:        %i  (%i f, %i m)\n',S.audinfo.hap.all,S.audinfo.hap.f,S.audinfo.hap.m);
strsca=sprintf('sca:        %i  (%i f, %i m)\n',S.audinfo.sca.all,S.audinfo.sca.f,S.audinfo.sca.m);

example1=sprintf('\n"000001_hap_m.wav"                             :happy;male\n');
example2=sprintf('"01abc_hap_M.wav"                               :happy;male\n');
example3=sprintf('"02abc_HAP_F.wav"                              :happy;female\n');
example4=sprintf('"abc001_Neu_m.wav"                            :neutral;male\n\n');
chc2=sprintf('Update File(name)s/Reselect Directory/Return to the main window');
choice = questdlg(['Carefully revise and confirm the following information about .wav files in the audio directory:'...
    ,str1,strf,strm,strhap,strsca,strneu,strsad,strang,...
    'The followings are some examples of interpretable input filenames(notice the ending pattern):',...
    example1,example2,example3,example4,...
    'If needed, rename the filenames accordingly.'],...
    'Confirmation', ...
    'Confirm',chc2,chc2);

S.audinfo.rms.recordings=zeros(1,S.audinfo.wav);
for i=1:S.audinfo.wav
    [y,~]=audioread([S.audir,'\',S.audiosshuffled{1,1}{1,i}]);
%     if S.ch(9).Value
%        y=(1/max(y))*(y) ; %normalizes highest amplitude to 1
%     end
    if S.ch(9).Value %Loudness normalization
        S.normcoef=max(y);
%         S.normcoef=rms(y);
        y=(1/S.normcoef)*y;        
    end
    
%     S.audinfo.rms.recordings(i)=rms(y); %'rms' requires Signal Processing Toolbox.
    S.audinfo.rms.recordings(i) = sqrt(nanmean(y.^2));
end
S.audinfo.rms.average=mean(S.audinfo.rms.recordings);
if numel(S.audinfo.rms.average)==2 %stereo input? make it mono
    S.audinfo.rms.average=mean(S.audinfo.rms.average);
end

S.audinfo.rms.stdev=std(S.audinfo.rms.recordings);
S.audinfo.rms.variability=100*S.audinfo.rms.stdev/S.audinfo.rms.average;

% Handle response

%if not called by calibrationmode.m
switch choice
    case 'Confirm'
        try %savestate(1,[],S)
            disp('confirmed')
            
            %             delete(S.fh2) %Closes figures
            %             delete(S.fh)
        catch err
            disp(err)
            %             disp(['Could not save the progress in ',S.ed(3).String,'\'])
        end
        yyy=S.audinfo;
        
    case chc2
        disp('not confirmed')
        if isfield(S,'fh')
            set(S.fh,'visible','on')
        end
        if isfield(S,'fh2')
            delete(S.fh2) %Closes figures
        end
        if isfield(S,'fh3')
            delete(S.fh3) %Closes figures
        end
        if isfield(S,'fhcalib')
            delete(S.fhcalib) %Closes figures
        end
        yyy=0;
        
        return
    otherwise %closed the confirmation dialogue?
        disp('closedconfirmation')
        
        if isfield(S,'fh')
            set(S.fh,'visible','on')
        end
        if isfield(S,'fh2')
            delete(S.fh2) %Closes figures
        end
        if isfield(S,'fh3')
            delete(S.fh3)
        end
        yyy=0;
        %         return
        
        %         try savestate(2,[],S)
        %         catch
        %         end
        %         if ~isempty(S.fh2)
        %             delete(S.fh2) %Closes figures
        %         end
        %         if ~isempty(S.fh)
        %             delete(S.fh)
        %         end
end




