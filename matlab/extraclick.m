function [] = extraclick(varargin)
%EXTRACLICK gets called only by pb_5emotions_call.m
%   Detailed explanation goes here
S=varargin{1,3};
% S.tstop=[];
% aa=varargin{}
LS=length(S.motives); %number of motivational senteces
% assignin('base','aaaa',varargin); %just to see the  properties in workspace
% if strcmp(varargin{1,2}.Source.Tag,'pbx')  %extra click has happened
% if varargin{1,3}{1,1}==1 %pbx called
% if get(S.tt(2),'val') && S.keypresscount>0 %training mode counter
% if S.audinfo.emoindsorted(S.keypresscount)~=str2double(S.caller(3))  %count the number of wrong choices in training mode
%     S.notrights=S.notrights+1;
% end
% end
if ~isempty(varargin{1,2})  %actiondata is reported, source must be pbx(extraclick push button)
    %     disp(11)
    if strcmp('Listen to the last played recording...',get(S.pb_extra,'String'))
        %         set(S.pbe,'visible','on','enable','off')
        %                         disp(1)
        
%         set(S.pbe,'visible','on','enable','off')
        
        for i=1:5
            if S.emo(i).Value
                set(S.pbe(i),'visible','on','enable','off')
            end
        end
        
%         set(S.pbe2,'visible','on','enable','off')
%         set(S.pbe3,'visible','on','enable','off')
%         set(S.pbe4,'visible','on','enable','off')
%         set(S.pbe5,'visible','on','enable','off')
        S.tstop=moh3nplayer([],[],S); %plays the recording, while gets back the Stop time of the playing
        S.instants=[S.instants;S.tstop];
        set(S.pb_pause,'call',{@pb_pauser,S});
        set(S.pb_extra,'call',{@extraclick,S})
        set(S.replayer, 'call', {@moh3nplayer,S})
        set(S.pbe,'callback',{@pb_5emotions_call,S})
%         set(S.pbe2,'callback',{@pb_5emotions_call,S})
%         set(S.pbe3,'callback',{@pb_5emotions_call,S})
%         set(S.pbe4,'callback',{@pb_5emotions_call,S})
%         set(S.pbe5,'callback',{@pb_5emotions_call,S})
        
        %         disp(111)
        %         S.tstop=[S.tstop,tttt];
        %         set(S.pb_extra,'visible','off')
    else
        if S.keypresscount>0 && isfield(S,'pbe')
            if get(S.tt(2),'val') && ~get(S.tt(3),'val') && S.audinfo.emoindsorted(S.keypresscount)~=S.keyspressed(S.keypresscount)%active training mode and wrong answer
%                 x=eval(sprintf('S.pbe%d',S.keyspressed(S.keypresscount)));
                set(S.pbe(S.keyspressed(S.keypresscount)),'visible','on','enable','off')
                set(S.replayer,'visible','on','enable','on','call', {@moh3nplayer,S})
                S.notrights=S.notrights+1;
            elseif S.tt(2).Value && S.tt(3).Value  %Passive Training
                if S.keypresscount < S.wavs
                    S.keypresscount=S.keypresscount+1; %count the number of calls
                    %                     bgchanger([],[],S)
                    bgchanger([],[],S)
                    
                    S.tstop=moh3nplayer(40,[],S);  %plays the recording, while gets back the Stop time of the playing
                    S.instants=[S.instants;S.tstop];
%                     tpush=[-1001,clock]; % tag for clicks : -1001
                    tpush=[-1001,now]; % tag for clicks : -1001
                    S.instants=[S.instants;tpush];
                    
                    S.keyspressed(S.keypresscount,1)=S.audinfo.emoindsorted(S.keypresscount);
%                     x=eval(sprintf('S.pbe%d',S.keyspressed(S.keypresscount)));
%                     pb_bg=S.pb_image{1,S.keyspressed(S.keypresscount)};
%                     pb_bg(:,:,1)=10;
%                     pb_bg(:,:,2)=1.5*pb_bg(:,:,2);
%                     pb_bg(:,:,3)=10;

                    set(S.pbe(S.keyspressed(S.keypresscount)),'visible','on','backgroundcolor',[0 0 1],...
                        'CData',S.pb_image_hi{1,S.keyspressed(S.keypresscount)})
                    pause(1)
                    set(S.pbe(S.keyspressed(S.keypresscount)),'visible','on','backgroundcolor',[1 1 1],...
                        'CData',S.pb_image{1,S.keyspressed(S.keypresscount)})
%                     assignin('base','pb',x)
                    
                    set(S.pbe,'call',[])
%                     set(S.pbe2,'call',[])
%                     set(S.pbe3,'call',[])
%                     set(S.pbe4,'call',[])
%                     set(S.pbe5,'call',[])
                    monitorperf([],'pb_5emotions_call.m',S)                    
                    extraclick([],'passivetraining',S)
                else
                    %                     S.tstop=moh3nplayer(40,[],S);  %plays the recording, while gets back the Stop time of the playing
                    %                     S.instants=[S.instants;S.tstop];
                    set(S.fh2,'visible','off')
                    uiwait(msgbox('Training is over. Please inform the experimenter.'))
                    savestate(4,[],S)
                end
                
                
                
            elseif ~get(S.tt(2),'val') || ... %not training
                    (get(S.tt(2),'val') && ~get(S.tt(3),'val')... %training and not passive
                    && S.audinfo.emoindsorted(S.keypresscount)==S.keyspressed(S.keypresscount))%have got the right answer in training)=
                
                
                %         disp(112)
                S.keypresscount=S.keypresscount+1; %count the number of calls
                %         x=S.keypresscount;
                %         disp(x)
                %         set(S.pbe,'visible','on','enable','off')
                
                %                 disp(2)
%                 set(S.pbe,'visible','on','enable','off')
                
                for i=1:5
                    if S.emo(i).Value
                        set(S.pbe(i),'visible','on','enable','off')
                    end
                end
                
                %                 set(S.pbe2,'visible','on','enable','off')
%                 set(S.pbe3,'visible','on','enable','off')
%                 set(S.pbe4,'visible','on','enable','off')
%                 set(S.pbe5,'visible','on','enable','off')
                
                %         set(S.pb_extra,'call',{@extraclick,S})
                %         set(S.pb_pause,'call',{@pb_pauser,S});
                %         set(S.replayer, 'call', {@moh3nplayer,S})
                %                 disp(1001)
                
                S.tstop=moh3nplayer(40,[],S);  %plays the recording, while gets back the Stop time of the playing
                S.instants=[S.instants;S.tstop];
                set(S.pb_pause,'call',{@pb_pauser,S});
                set(S.pb_extra,'call',{@extraclick,S})
                set(S.replayer, 'call', {@moh3nplayer,S})
                set(S.pbe,'call',{@pb_5emotions_call,S})
%                 set(S.pbe2,'call',{@pb_5emotions_call,S})
%                 set(S.pbe3,'call',{@pb_5emotions_call,S})
%                 set(S.pbe4,'call',{@pb_5emotions_call,S})
%                 set(S.pbe5,'call',{@pb_5emotions_call,S})
                
                %         S.tstop=moh3nplayer([],[],S);  %plays the recording, while gets back the Stop time of the playing
                %             S.tstop=tstop;
                
            end
            
        else  %S.keypresscount=[]: only for the first click
            %                             disp(1002)
            
            S.keypresscount=S.keypresscount+1; %count the number of calls
            
%             set(S.pbe,'visible','on','enable','off')
            for i=1:5
                if S.emo(i).Value
                    set(S.pbe(i),'visible','on','enable','off')
                end
            end
            %             set(S.pbe2,'visible','on','enable','off')
            %             set(S.pbe3,'visible','on','enable','off')
            %             set(S.pbe4,'visible','on','enable','off')
            %             set(S.pbe5,'visible','on','enable','off')
            %             end
            %         set(S.pb_extra,'call',{@extraclick,S})
            %         set(S.pb_pause,'call',{@pb_pauser,S});
            %         set(S.replayer, 'call', {@moh3nplayer,S})
            S.tstop=moh3nplayer(40,[],S);  %plays the recording, while gets back the Stop time of the playing
            S.instants=[S.instants;S.tstop];
            set(S.pb_pause,'call',{@pb_pauser,S});
            set(S.pb_extra,'call',{@extraclick,S})
            set(S.replayer, 'call', {@moh3nplayer,S})
            set(S.pbe,'call',{@pb_5emotions_call,S})
%             set(S.pbe2,'call',{@pb_5emotions_call,S})
%             set(S.pbe3,'call',{@pb_5emotions_call,S})
%             set(S.pbe4,'call',{@pb_5emotions_call,S})
%             set(S.pbe5,'call',{@pb_5emotions_call,S})
            
            if S.tt(2).Value && S.tt(3).Value && isfield(S,'pbe')  %Passive Training?
%                 tpush=[-1001,clock]; % tag for clicks : -1001
                tpush=[-1001,now]; % tag for clicks : -1001
                S.instants=[S.instants;tpush];
                S.keypresscount=1; %count the number of calls
                bgchanger([],[],S)
                disp(S.keypresscount)
                %                     S.tstop=moh3nplayer(40,[],S);  %plays the recording, while gets back the Stop time of the playing
                %                     S.instants=[S.instants;S.tstop];

                S.keyspressed(S.keypresscount,1)=S.audinfo.emoindsorted(S.keypresscount);
%                 x=eval(sprintf('S.pbe%d',S.keyspressed(S.keypresscount)));
                    set(S.pbe(S.keyspressed(S.keypresscount)),'visible','on','backgroundcolor',[0 0 1],...
                        'CData',S.pb_image_hi{1,S.keyspressed(S.keypresscount)})
                    pause(1)
                    set(S.pbe(S.keyspressed(S.keypresscount)),'visible','on','backgroundcolor',[1 1 1],...
                        'CData',S.pb_image{1,S.keyspressed(S.keypresscount)})
%                 assignin('base','pb',x)
                
                set(S.pbe,'call',[])
%                 set(S.pbe2,'call',[])
%                 set(S.pbe3,'call',[])
%                 set(S.pbe4,'call',[])
%                 set(S.pbe5,'call',[])
                monitorperf([],'pb_5emotions_call.m',S)
                extraclick([],'passivetraining',S)
                

            end
            
        end
        
        
        %         S.tstop=[S.tstop,tttt];
        %         set(S.pb_extra,'visible','off')
        
        %     set(S.pbe,'enable','off')
    end
    % elseif varargin{1,2}==1   %pbe called
elseif isempty(varargin{1,2})&& get(S.ch(2),'val') %extra click is active
    %     disp(22)
    %no action data is reported
    if get(S.tt(2),'val') && S.audinfo.emoindsorted(S.keypresscount)~=S.keyspressed(S.keypresscount)%training mode and wrong answer
%         x=eval(sprintf('S.pbe%d',S.keyspressed(S.keypresscount)));
        set(S.pbe(S.keyspressed(S.keypresscount)),'visible','on','enable','off')
        set(S.replayer,'visible','on','enable','on','call', {@moh3nplayer,S})
        S.notrights=S.notrights+1;
        
    elseif ~get(S.tt(2),'val') || S.audinfo.emoindsorted(S.keypresscount)==S.keyspressed(S.keypresscount)%not in training mode or have got the right answer in training
        
        
        set(S.pb_extra,'visible','on','enable','on')
        if get(S.ch(1),'value')
            set(S.replayer,'visible','off','enable','off')
            set(S.led,'visible','off')
        end
        set(S.pb_extra,'string',...
            S.motives(ceil(LS*rand(1))))  %shows random motivational sentence on the pbx button
        %     moh3nplayer([],[],S)
        %     if round(S.keypresscount/S.intervl)==S.keypresscount/S.intervl
        set(S.pb_pause,'call',{@pb_pauser,S});
        set(S.pb_extra,'call',{@extraclick,S})
        set(S.replayer, 'call', {@moh3nplayer,S})
        set(S.pbe,'callback',{@pb_5emotions_call,S})
%         set(S.pbe2,'callback',{@pb_5emotions_call,S})
%         set(S.pbe3,'callback',{@pb_5emotions_call,S})
%         set(S.pbe4,'callback',{@pb_5emotions_call,S})
%         set(S.pbe5,'callback',{@pb_5emotions_call,S})
        bgchanger([],[],S)
        %     if ~exist('tttt','var')
        %     tttt=[];
        %     end
        %     end
    end
elseif  isempty(varargin{1,2})&& ~get(S.ch(2),'val') %extra click inactive, plays the next recording right after selecting the answer
    %     disp(33)
    %     bgchanger([],[],S)
    if S.keypresscount<S.audinfo.wav %Check to see if the test is over yet
        %         disp(331)
        
        if get(S.tt(2),'val') && S.audinfo.emoindsorted(S.keypresscount)~=S.keyspressed(S.keypresscount)%training mode and wrong answer
%             x=eval(sprintf('S.pbe%d',S.keyspressed(S.keypresscount)));
            set(S.pbe(S.keyspressed(S.keypresscount)),'visible','on','enable','off')
            set(S.replayer,'visible','on','enable','on','call', {@moh3nplayer,S})
            S.notrights=S.notrights+1;
            
        elseif ~get(S.tt(2),'val') || S.audinfo.emoindsorted(S.keypresscount)==S.keyspressed(S.keypresscount)%not in training mode or have got the right answer in training
            bgchanger([],[],S)
            S.keypresscount=S.keypresscount+1;
            
            %     if S.keypresscount<S.audinfo.wav %Check to see if the test is over yet
            set(S.replayer,'visible','off','enable','off')
            
            S.tstop=moh3nplayer([],[],S);  %plays the recording, while gets back the Stop time of the playing
            %     end
            S.instants=[S.instants;S.tstop];
            set(S.pb_pause,'call',{@pb_pauser,S});
            
            set(S.pb_extra, 'call'      ,{@extraclick,S})
            set(S.replayer, 'call'      , {@moh3nplayer,S})
            set(S.pbe,      'callback'  ,{@pb_5emotions_call,S})
%             set(S.pbe2,'callback',{@pb_5emotions_call,S})
%             set(S.pbe3,'callback',{@pb_5emotions_call,S})
%             set(S.pbe4,'callback',{@pb_5emotions_call,S})
%             set(S.pbe5,'callback',{@pb_5emotions_call,S})
        end
        
    else
        if get(S.tt(2),'val') && S.audinfo.emoindsorted(S.keypresscount)~=S.keyspressed(S.keypresscount)%training mode and wrong answer
%             x=eval(sprintf('S.pbe%d',S.keyspressed(S.keypresscount)));
            set(S.pbe(S.keyspressed(S.keypresscount)),'visible','on','enable','off')
            set(S.replayer,'visible','on','enable','on','call', {@moh3nplayer,S})
            S.notrights=S.notrights+1;
            
        elseif ~get(S.tt(2),'val') || S.audinfo.emoindsorted(S.keypresscount)==S.keyspressed(S.keypresscount)%not in training mode or have got the right answer in training
            
            %         disp(332)
            set(S.replayer,'visible','off','enable','off')
            %     if S.keypresscount<S.audinfo.wav %Check to see if the test is over yet
            S.tstop=moh3nplayer(46,[],S);  %46: special case for the end of the task
            S.instants=[S.instants;S.tstop];
        end
    end
    %     S.tstop=[S.tstop,tttt];
    
else
    disp('unexpected error_extraclick.m')
    %     tttt=[];
end
% tttt=[];
% if ~isempty(varargin{1,2})
%     disp(44)
%     S.stopinstant=[S.stopinstant;S.tstop];
% %     S.instants=[S.instants;S.tstop];
%
%     % if get(S.ch5,'val')  %performance monitor? report the stuff!
%     %     monitorperf([],'extraclick.m',S)
%     % end
%
% end
% S.instants=[S.instants;S.tstop];
% set(S.pb_pause,'call',{@pb_pauser,S});
%
% set(S.pb_extra,'call',{@extraclick,S})
% set(S.replayer, 'call', {@moh3nplayer,S})
% set(S.pbe1,'callback',{@pb_5emotions_call,S})
% set(S.pbe2,'callback',{@pb_5emotions_call,S})
% set(S.pbe3,'callback',{@pb_5emotions_call,S})
% set(S.pbe4,'callback',{@pb_5emotions_call,S})
% set(S.pbe5,'callback',{@pb_5emotions_call,S})
% set(S.pb_pause,'call',{@pb_pauser,S});

%     set(S.pb_extra,'visible','on')
