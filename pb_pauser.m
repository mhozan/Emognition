function [S]=pb_pauser(varargin)

S=varargin{1,3};

if strcmp(get(S.pb_pause,'string'),'Pause...')
%     tt=[-9999,clock];   %9999tag for stop instant(end of audio playing)
    tt=[-9999,now];   %9999tag for stop instant(end of audio playing)
    S.tpause=[S.tpause;tt];
    S.instants=[S.instants;tt];
%     assignin('base','instantz',S.instants)
%                         disp(111)

    %     S.visibility1=get(S.pbe(1),'enable');
    if get(S.ch(2),'val')  %pb_extra?
%         disp(111000)
        S.visibility2=get(S.pb_extra,'visible');
    end
    %     S.visibility3=get(S.replayer,'visible');
    %     S.visibility4=get(S.led,'visible');

    set(S.pb_pause,'string','Resume...')
    %     set(S.pbe,'visible','off')
    set(S.pbe,'visible','off')
%     set(S.pbe2,'visible','off')
%     set(S.pbe3,'visible','off')
%     set(S.pbe4,'visible','off')
%     set(S.pbe5,'visible','off')
    set(S.pb_extra,'visible','off')
    set(S.led,'visible','off')
    set(S.replayer,'visible','off')
    
elseif strcmp(get(S.pb_pause,'string'),'Resume...')
%     tt=[-9998,clock];  %9998tag for resume instant
    tt=[-9998,now];  %9998tag for resume instant
    
    S.tresume=[S.tresume;tt];
    S.instants=[S.instants;tt];
    assignin('base','instantz',S.instants)
%                         disp(11100)

    %     aa= S.visibility2;
    %     assignin('base',S.visibility2,'svisibility2')
    %     S.visibility2=get(S.pb_extra,'visible');
    if get(S.ch(2),'val') %extra click?
        switch S.visibility2
            case 'on'
                if get(S.ch(2),'val')
                    %                                         disp(1110001)
                    
                    set(S.pb_extra,'visible','on')
                end
                %                 set(S.pbe,'visible','on')
                for i=1:5
                    if S.emo(i).Value
                        set(S.pbe(i),'visible','on')
                    end
                end
                %                 set(S.pbe2,'visible','on')
                %                 set(S.pbe3,'visible','on')
                %                 set(S.pbe4,'visible','on')
                %                 set(S.pbe5,'visible','on')
                %                 disp(1121)
                
                
            case 'off'
                %                 set(S.pbe,'visible','on')
                for i=1:5
                    if S.emo(i).Value
                        set(S.pbe(i),'visible','on')
                    end
                end
                
                %                 set(S.pbe,'visible','on')
%                 set(S.pbe2,'visible','on')
%                 set(S.pbe3,'visible','on')
%                 set(S.pbe4,'visible','on')
%                 set(S.pbe5,'visible','on')
%                 disp(1122)

                if get(S.ch(3),'val')
                    set(S.led,'visible','on')
                end
                if get(S.ch(1),'val')  %Replays allowed?
                    set(S.replayer,'visible','on','enable','on')
%                     disp(1122222)
                end
            otherwise
                disp('Something''s not right')
        end
        
        if ~get(S.ch(1),'val')  %replays the latest recording after a pause in case replays are not allowed
%                             disp(113)

            %             pause(1)
            %             pb_5emotions_call([],[],S)
            set(S.pb_extra,'visible','on')
            set(S.pb_extra,'enable','on')
            
            %             set(S.pbe,'visible','off')
            set(S.pbe,'visible','off')
%             set(S.pbe2,'visible','off')
%             set(S.pbe3,'visible','off')
%             set(S.pbe4,'visible','off')
%             set(S.pbe5,'visible','off')
            set(S.pb_extra,'String','Listen to the last played recording...')
            %             set(S.pb_pause,'call',{@pb_pauser,S})
            
            %             set(S.pb_extra,'UserData','rarecase')
        end
        
        
    elseif ~get(S.ch(2),'val')
        disp(114)
        %         set(S.pbe,'visible','on')
                for i=1:5
                    if S.emo(i).Value
                        set(S.pbe(i),'visible','on')
                    end
                end
%         set(S.pbe,'visible','on')
%         set(S.pbe2,'visible','on')
%         set(S.pbe3,'visible','on')
%         set(S.pbe4,'visible','on')
%         set(S.pbe5,'visible','on')
        set(S.pb_extra,'visible','off')
        if get(S.ch(3),'val')  %LED?
            set(S.led,'visible','on')
        end
        if get(S.ch(1),'val')
%             disp(115)
            set(S.replayer,'visible','on')
        end
        if ~get(S.ch(1),'val')  %replays the latest recording after a pause in case replays are not allowed
%             disp(116)
            %             pause(1)
            %             pb_5emotions_call([],[],S)
            set(S.pb_extra,'visible','on')
            set(S.pb_extra,'enable','on')
            
            %             set(S.pbe,'visible','off')
            set(S.pbe,'visible','off')
%             set(S.pbe2,'visible','off')
%             set(S.pbe3,'visible','off')
%             set(S.pbe4,'visible','off')
%             set(S.pbe5,'visible','off')
            set(S.pb_extra,'String','Listen to the last played recording...')
            %             set(S.pb_pause,'call',{@pb_pauser,S})
            
            %             set(S.pb_extra,'UserData','rarecase')
        end
    end
    set(S.pb_pause,'string','Pause...')
    
    
    
else
    
    disp('Something''s not right...pb_pauser.m')
    
end
% if get(S.ch5,'val')  %performance monitor? report the stuff!
%     monitorperf([],'pb_pauser.m',S)
% end
set(S.pb_pause,'call',{@pb_pauser,S})
set(S.pbe,'callback',{@pb_5emotions_call,S})
% set(S.pbe2,'callback',{@pb_5emotions_call,S})
% set(S.pbe3,'callback',{@pb_5emotions_call,S})
% set(S.pbe4,'callback',{@pb_5emotions_call,S})
% set(S.pbe5,'callback',{@pb_5emotions_call,S})
set(S.replayer, 'call', {@moh3nplayer,S})
set(S.pb_extra,'call',{@extraclick,S})

% allvars=S;
% if ~get(S.ch4,'val')
%     xbility=get(S.pbe(1),'enable');
% else
%     xbility=get(S.pb_extra,'visible');
% end
% % if S.keypresscount <= 3
% %     set(S.pb_pause,'visible','off');
% % else
% %     set(S.pb_pause,'visible','on');
% if strcmp(xbility,'on')
%     disp('Paused...')
%     set(S.pbe(:),'visible','off','enable','off')
%     set(S.replayer(:),'visible','off','enable','off')
%     set(S.led,'visible','off')
%     set(S.pb_pause,'string','Resume...')
%     set(S.pb_extra,'visible','off')
%
% elseif strcmp(xbility,'off')
%     disp('Resumed...')
%     %     pause(.1)
%     set(S.pbe(:),'visible','on','enable','on')
%     set(S.led,'visible','on')
%     set(S.pb_pause,'string','Pause...')
%     %     if S.keypresscount ~= 0
%     set(S.replayer(:),'visible','on','enable','on')
%     if get(S.ch4,'val') && strcmp(get(S.pbe(1),'enable'),'off')
%         set(S.pb_extra,'visible','on')
%     end
%     %     end
% else
%     %do nothing
%     disp('pb_pauser.m error')
% end
% % end
% set(S.pb_pause,'call',{@pb_pauser,S});
