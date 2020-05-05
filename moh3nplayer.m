function [tstop] = moh3nplayer(varargin)
%   plays the wav files, gets called by S.replayer pushbutton and extraclick.m
%   assignin('base','Smoh3nplayer',varargin); %just to see the  properties in workspace
set(varargin{1,3}.replayer,'visible','off','enable','off');
set(varargin{1,3}.pb_extra,'visible','off','enable','off');
drawnow  %prevents multiple clicks
S=varargin{1,3};
%   set(S.replayer,'visible','off')
%   set(S.pb_extra,'visible','off')
if ~isempty(varargin{1,1})
    firstinput=varargin{1,1}; %usually empty, sometimes 40, sometimes 46
else
    firstinput=0;
end
%   MOH3NPLAYER
%   a=nargin
%   assignin('base','S',S); %just to see the  properties in workspace


% X=varargin;
caller=varargin{1,2};
% if ~isempty(caller)  %this is to prevent S.replayinstant to be cleared
%     S=varargin{1,3};
% end


% assignin('base','X',X); %just to see the  properties in workspace




% audio2BEplayed=audioread([S.bgdir,'\',S.picsshuffled{1,1}{1,indx}]);


% if S.keypresscount>S.audinfo.wav
%     return
% else

[y,Fs]=audioread([S.audir,'\',S.audiosshuffled{1,1}{1,S.keypresscount}]);
% if S.ch(9).Value %Loudness normalization
%    y=(1/max(y))*y;
% end
    if S.ch(9).Value %Loudness normalization
        S.normcoef=max(y);
%         S.normcoef=rms(y);
        y=(1/S.normcoef)*y;        
    end
% S.pobj=audioplayer(y,Fs);
if firstinput==46 %this only happens when extraclick is deactive and prevents the last recording to be played twice
    %     S.pobj=audioplayer(zeros(1,10),Fs,16,1);% audioplayer(Y,Fs,nBits,ID)
    S.pobj=audioplayer(zeros(100,1),Fs);    
else
    %     S.pobj=audioplayer(y,Fs,16,1); % audioplayer(Y,Fs,nBits,ID)
    S.pobj=audioplayer(y,Fs);        
end

% y2=lin2mu(y);
% disp(S.keypresscount)
if get(S.ch(3),'val')  %&& S.keypresscount<=S.audinfo.wav%checks the LED volume indicator checkbox
    y2=abs(y);
    ymax=max(y2);
    y2=y2/ymax; %normalize to [0,1] range
    
    for i=1:length(y2) %5 volume bar levels
        if y2(i)<0.01*ymax
            y2(i)=0.1;
        elseif ((y2(i)>=.01) && (y2(i)<.1))
            y2(i)=.4;
        elseif ((y2(i)>=.1) && (y2(i)<.25))
            y2(i)=.6;
        elseif ((y2(i)>=.25) && (y2(i)<.4))
            y2(i)=.75;
        elseif ((y2(i)>=.4) && (y2(i)<.65))
            y2(i)=.9;
        else
            y2(i)=1;
        end
    end
    
    S.pobj.UserData.audio=y2;
    set(S.pobj,'TimerPeriod',.1,...
        'TimerFcn',{@volumeLED,S})
    set(S.led,'visible','on')
    
end
set(S.pobj,'StopFcn',@enablebutton); %enablebutton also records the end of the audio playing
playblocking(S.pobj)
disp(['Played: ',S.audir,'\',S.audiosshuffled{1,1}{1,S.keypresscount}])
% disp('reached 89 moh3nplayer')
% if isempty(caller)
%     set(S.replayer, 'call', {@moh3nplayer,S})
%                     set(S.pb_pause,'call',{@pb_pauser,S});

% else
%do nothing! the callback will be set in line ~89
%     set(S.replayer, 'call', {@moh3nplayer,S})
% end
% a=played.CurrentSample

% while strcmp(pobj.Running,'on')
%     for i=1:1000
%         pause(0.1)
%     end
% end
% end  %if
    function []=enablebutton(varargin)
        %         S=varargin{1,3};
%         tstop=[-1002,clock]; %-1002 tag for stop instant
        tstop=[-1002,now];
        if strcmp('Listen to the last played recording...',get(S.pb_extra,'String'))
            tstop(1)=-1008; %tag for a sepcial Replay instant
%             S.instants=[S.instants;tstop];
            
            %                                 set(SS.replayer, 'call', {@moh3nplayer,SS})  %Keeps the S updatede
            set(S.pbe,'callback',{@pb_5emotions_call,S})
            set(S.pb_extra,'call',{@extraclick,S})
            
            set(S.pb_pause,'call',{@pb_pauser,S});
            set(S.replayer, 'call', {@moh3nplayer,S})
            set(S.pb_extra,'String','okay!')
        end
        if ~isempty(caller)
            tstop(1)=-1009;    %-1009: tag for replay instant
            if strcmp(caller.Source.Tag,'replayer')  %Moh3nplayer gets occasionally called by S.replayer push button
                %                 disp(tt)
                S.replayinstants=[S.replayinstants;tstop];
                %                 if get(SS.ch5,'val')  %performance monitor? report the stuff!
                %                 monitorperf([],'moh3nplayer.m',SS)
                %                 end
                S.instants=[S.instants;tstop];
                
                %                                 set(SS.replayer, 'call', {@moh3nplayer,SS})  %Keeps the S updatede
                if get(S.tt(2),'val')
                    %do nothing
                    %                     if ~get(S.ch(2),'val') %no extraclick ?
                    %                         set(S.pbe1,'callback',{@pb_5emotions_call,S})
                    %                         set(S.pbe2,'callback',{@pb_5emotions_call,S})
                    %                         set(S.pbe3,'callback',{@pb_5emotions_call,S})
                    %                         set(S.pbe4,'callback',{@pb_5emotions_call,S})
                    %                         set(S.pbe5,'callback',{@pb_5emotions_call,S})
                    %                     end
                    
                else% not in training mode? count the replays and stuff!
                    set(S.pbe,'callback',{@pb_5emotions_call,S})
%                     set(S.pbe2,'callback',{@pb_5emotions_call,S})
%                     set(S.pbe3,'callback',{@pb_5emotions_call,S})
%                     set(S.pbe4,'callback',{@pb_5emotions_call,S})
%                     set(S.pbe5,'callback',{@pb_5emotions_call,S})
                end
                set(S.pb_extra,'call',{@extraclick,S})
                set(S.pb_pause,'call',{@pb_pauser,S});
                set(S.replayer, 'call', {@moh3nplayer,S})
            end
        end
        %         playingstoptime(tt)
        %         yyyyy=[yyyyy;tt];  %will be used in calculating reaction time
        
        %
        %         set(S.pbe,'visible','on')
        %         set(S.pbe,'enable','on')
        
        
        % x=varargin{1,1};
        if get(S.tt(2),'val') && S.keypresscount >= 1 &&  get(S.ch(2),'val') && ~(firstinput==40) %training && extraclick off or it is a replay if it is on
            %             if (S.audinfo.emoindsorted(S.keypresscount)~=S.keyspressed(S.keypresscount))
            %                 disp(1)
            %             set(S.pbe,'visible','on')
            for jj=1:5
                if S.emo(jj).Value
                    set(S.pbe(jj),'visible','on')
%                     set(S.pbe(jj),'visible','on','enable','on')
                end
            end
            %             set(S.pbe2,'visible','on')
            %             set(S.pbe3,'visible','on')
            %             set(S.pbe4,'visible','on')
%             set(S.pbe5,'visible','on')
            %             else
            %                 disp(2)
            % if firstinput==40
            % %     disp(866)
            %             set(S.pbe1,'enable','on')
            %             set(S.pbe2,'enable','on')
            %             set(S.pbe3,'enable','on')
            %             set(S.pbe4,'enable','on')
            %             set(S.pbe5,'enable','on')
            % end
            %             set(S.pbe1,'visible','on','enable','on')
            %             set(S.pbe2,'visible','on','enable','on')
            %             set(S.pbe3,'visible','on','enable','on')
            %             set(S.pbe4,'visible','on','enable','on')
            %             set(S.pbe5,'visible','on','enable','on')
            %             end
            
        elseif  get(S.tt(2),'val') && S.keypresscount >= 1 && ~isempty(caller) && ~get(S.ch(2),'val') %training, no extra click and we've got a replay
            % %             disp(4444456)
            %               %to avoid resetting
            %                 disp('here')
%             set(S.pbe,'visible','on')
            for jj=1:5
                if S.emo(jj).Value
                    set(S.pbe(jj),'visible','on')
%                     set(S.pbe(jj),'visible','on','enable','on')
                end
            end            
%             set(S.pbe2,'visible','on')
%             set(S.pbe3,'visible','on')
%             set(S.pbe4,'visible','on')
%             set(S.pbe5,'visible','on')
        else
%             set(S.pbe,'visible','on','enable','on')
            for jj=1:5
                if S.emo(jj).Value
                    set(S.pbe(jj),'visible','on','enable','on')
                end
            end
            %             set(S.pbe2,'visible','on','enable','on')
%             set(S.pbe3,'visible','on','enable','on')
%             set(S.pbe4,'visible','on','enable','on')
%             set(S.pbe5,'visible','on','enable','on')
            
        end
        if get(S.ch(1),'value') && S.keypresscount >= 1
            set(S.replayer,'visible','on','enable','on')
        end
        if S.keypresscount >= 3   && ~get(S.tt(2),'val')%enable PAUSE button for the test after 3 questions, if not in training
            set(S.pb_pause,'enable','on')
            
        end
        
        
    end
%             set(S.pb_pause,'call',{@pb_pauser,S});

% set(S.replayer, 'call', {@moh3nplayer,S})  %Keeps the S updatede
% allvars=S;
end
%
% set(S.pbe1,'callback',{@pb_5emotions_call,S})
% set(S.pbe2,'callback',{@pb_5emotions_call,S})
% set(S.pbe3,'callback',{@pb_5emotions_call,S})
% set(S.pbe4,'callback',{@pb_5emotions_call,S})
% set(S.pbe5,'callback',{@pb_5emotions_call,S})
% set(S.pb_pause,'call',{@pb_pauser,S});
% set(S.replayer, 'call', {@moh3nplayer,S})
% set(S.pb_extra,'call',{@extraclick,S})


% end


% %MOH3NPLAYER
% S=varargin{1,3};
% % [y,Fs]=audioread('sampleaudio.wav');
% % S=varargin{3};
% [y,Fs]=audioread('sampleaudio.wav');
% % S.pobj=audioplayer(y,Fs);
% S.pobj=audioplayer(y,Fs);
%
% % y2=lin2mu(y);
% y2=abs(y);
% ymax=max(y2);
% y2=y2/ymax; %normalize between 0,1
% for i=1:length(y2) %5 volume bar levels
%     if y2(i)<0.01*ymax
%         y2(i)=0.2;
%     elseif ((y2(i)>=.01) && (y2(i)<.1))
%         y2(i)=.4;
%     elseif ((y2(i)>=.1) && (y2(i)<.25))
%         y2(i)=.6;
%     elseif ((y2(i)>=.25) && (y2(i)<.4))
%         y2(i)=.75;
%     elseif ((y2(i)>=.4) && (y2(i)<.65))
%         y2(i)=.9;
%     else
%         y2(i)=1;
%     end
% end
%
%
% % y2(y2<.2)=0;
% % y2((y2>=.2) & (y2<.4))=1;
% % y2((y2>=.4) & (y2<.6))=2;
% % y2((y2>=.6) & (y2<.8))=3;
% % y2(y2>=.8)=4;
%
% S.pobj.UserData.audio=y2;
% % pobj.CurrentSample
% % pobj.UserData=y2(pobj.CurrentSample);
%
% %    pobj.TimerFcn = 'showSeconds';
% %    pobj.TimerPeriod = .1;
% set(S.pobj,'TimerPeriod',.005,...
%     'TimerFcn',{@volumebar,S});
%
% % get(pobj,'CurrentSample')
%
% end
%
%
%
% % playblocking(pobj)
% % a=played.CurrentSample
%
% % while strcmp(pobj.Running,'on')
% %     for i=1:1000
% %         pause(0.1)
% %     end
% % end
%
%
%
% % end
%
