function [] = pb_5emotions_call(varargin)
% set(varargin{1,3}.pbe,'enable','off')
% set(varargin{1,3}.pbe1,'enable','off')
% set(varargin{1,3}.pbe2,'enable','off')
% set(varargin{1,3}.pbe3,'enable','off')
% set(varargin{1,3}.pbe4,'enable','off')
% set(varargin{1,3}.pbe5,'enable','off')
% tpush=[-1001,clock]; % tag for clicks : -1001
tpush=[-1001,now]; % tag for clicks : -1001
S=varargin{1,3};
S.instants=[S.instants;tpush];
S.caller=[];
if get(S.tt(2),'val') %&& S.keypresscount>0 % Training mode
    actiondata=varargin{1,2};
    S.caller=actiondata.Source.Tag;
%     disp(S.caller)
    
    if S.audinfo.emoindsorted(S.keypresscount)~=str2double(S.caller(3))
%         rtry=rtry+1;
%         disp(rtry)
%         x=eval(['S.pbe',S.caller(3)]);
        %         S.Retries=S.Retries+1; %count the number of mistakes in training mode
        %         a=S.Retries;
        %         disp(a)
        set(S.pbe(str2double(S.caller(3))),'visible','on','enable','off') %only disables the wrong answer
    else
        set(S.pbe,'enable','off')

    end
else
    
    set(S.pbe,'enable','off')

end
drawnow  %very crucial line! prevents repetetive clicks on push buttons




% assignin('base','inputz',S); %just to see the  properties in workspace

% S.keypresscount=S.keypresscount+1; %count the number of calls
% cntr=S.keypresscount
if ~isempty(varargin{1,2})
    S.pushinstant=[S.pushinstant;tpush];
    %     S.instants=[S.instants;tpush];
    %     S.keypresscount=S.keypresscount+1; %count the number of calls
    
    actiondata=varargin{1,2};
    %     assignin('base','actionD',varargin); %just to see the  properties in workspace
    
    % keyspressed=S.keyspressed;
    S.caller=actiondata.Source.Tag; %Which button called? 
    % MATLAB 2014a cannot understand this! 2014b can!
    % actiondata=actiondata.Source;
    % caller=get(actiondata,'Tag');
    % disp([caller(3),' got pushed!'])
    %     assignin('base','callllll',caller(3))
    switch S.caller(3)  %read the 3rd character in the tag names
        case '1'
            if get(S.tt(2),'val') && S.keypresscount>0% Training mode
                
                if S.audinfo.emoindsorted(S.keypresscount)==1
                    S.keyspressed=[S.keyspressed;1];
                else
%                     S.Retries=S.Retries+1; %count the number of mistakes in training mode
%                     a=S.Retries;
%                     disp(a)
                    S.keyspressed(S.keypresscount)=1; %S.keyspressed(S.keypresscount)=1;
                end
            else
                S.keyspressed=[S.keyspressed;1];
            end
            %          set(S.pbe(1),'call',{@pb_5emotions_call,S}); %updates the keys and values
        case '2'
            if get(S.tt(2),'val') && S.keypresscount>0% Training mode
                
                if S.audinfo.emoindsorted(S.keypresscount)==2
                    S.keyspressed=[S.keyspressed;2];
                else
%                     S.Retries=S.Retries+1; %count the number of mistakes in training mode
%                     a=S.Retries;
%                     disp(a)
                    S.keyspressed(S.keypresscount)=2; %S.keyspressed(S.keypresscount)=1;
                end
            else
                S.keyspressed=[S.keyspressed;2];
            end
            %          set(S.pbe(2),'call',{@pb_5emotions_call,S}); %updates the keys and values
        case '3'
            if get(S.tt(2),'val') && S.keypresscount>0% Training mode
                
                if S.audinfo.emoindsorted(S.keypresscount)==3
                    S.keyspressed=[S.keyspressed;3];
                else
%                     S.Retries=S.Retries+1; %count the number of mistakes in training mode
%                     a=S.Retries;
%                     disp(a)
                    S.keyspressed(S.keypresscount)=3; %S.keyspressed(S.keypresscount)=1;
                end
            else
                S.keyspressed=[S.keyspressed;3];
            end            %          set(S.pbe(3),'call',{@pb_5emotions_call,S}) %updates the keys and values
        case '4'
            if get(S.tt(2),'val') && S.keypresscount>0% Training mode
                
                if S.audinfo.emoindsorted(S.keypresscount)==4
                    S.keyspressed=[S.keyspressed;4];
                else
%                     S.Retries=S.Retries+1; %count the number of mistakes in training mode
%                     a=S.Retries;
%                     disp(a)
                    S.keyspressed(S.keypresscount)=4; %S.keyspressed(S.keypresscount)=1;
                end
            else
                S.keyspressed=[S.keyspressed;4];
            end            %          set(S.pbe(4),'call',{@pb_5emotions_call,S}) %updates the keys and values
        case '5'
            if get(S.tt(2),'val') && S.keypresscount>0% Training mode
                
                if S.audinfo.emoindsorted(S.keypresscount)==5
                    S.keyspressed=[S.keyspressed;5];
                else
%                     S.Retries=S.Retries+1; %count the number of mistakes in training mode
%                     a=S.Retries;
%                     disp(a)
                    S.keyspressed(S.keypresscount)=5; %S.keyspressed(S.keypresscount)=1;
                end
            else
                S.keyspressed=[S.keyspressed;5];
            end            %          set(S.pbe(5),'call',{@pb_5emotions_call,S}) %updates the keys and values
            %     case 'l'
            %         disp('ya ghamar')
        otherwise %pb_pause  has called
            disp('pb_5emotions_call has encoutered an unexpected errorline102')
            
            %this should not happen
    end
    
elseif isempty(varargin{1,2}) %pb_pause is calling in a rare occasion
    %             S.keyspressed=[S.keyspressed];
    %             S.keypresscount=S.keypresscount; %nothing happens basically
    % v = evalin('base', 'pressed_keys');
    %             S.keypresscount=length(v);
    disp('pb_5emotions_call has encoutered an unexpected error line145')
    
end


% S.keyspressed=keyspressed;

%


% set(S.pbe(:),'call',{@pb_5emotions_call,S}) %updates the keys and values



% set(S.pbe(:),'callback',{@moh3nplayer,S})
% assignin('base','pressed_keys',S.keyspressed); %just to see the  properties in workspace

% set(S.pb_extra,'visible','on')
% moh3nplayer([],[],S)
% if S.keypresscount==3  %enable save after a few answers
set(S.fh2,'closerequestfcn',{@rusure,S})
% if isfield(S,'fh3')
%     if ~isempty(S.fh3) %make sure the performance monitor window is not closed
%     set(S.fh3,'closerequestfcn',{@rusure,S})
%     end
% end
% end

%
% set(S.pbe1,'callback',{@pb_5emotions_call,S})
% set(S.pbe2,'callback',{@pb_5emotions_call,S})
% set(S.pbe3,'callback',{@pb_5emotions_call,S})
% set(S.pbe4,'callback',{@pb_5emotions_call,S})
% set(S.pbe5,'callback',{@pb_5emotions_call,S})
% set(S.pb_pause,'call',{@pb_pauser,S});
% set(S.replayer, 'call', {@moh3nplayer,S})
% set(S.pb_extra,'call',{@extraclick,S})

% S.stopinstant=[S.stopinstant;tttt];

% if get(S.ch5,'val')  %performance monitor? report the stuff!
% extraclick([],[],S)  %report the caller


if get(S.tt(2),'val') && S.keypresscount>0% S.audinfo.emoindsorted(S.keypresscount)~=S.keyspressed(S.keypresscount)
    
    if S.audinfo.emoindsorted(S.keypresscount)==S.keyspressed(S.keypresscount)
        monitorperf([],'pb_5emotions_call.m',S)
    else
        %         disp('errorline119_pb5_emotions_call.m')
    end
    
else
    monitorperf([],'pb_5emotions_call.m',S)
end
extraclick([],[],S)  %report the caller

% set(S.pb_pause,'call',{@pb_pauser,S});
% set(S.replayer, 'call', {@moh3nplayer,S})
% set(S.pb_extra,'call',{@extraclick,S})

if S.keypresscount>=S.audinfo.wav %last question
    %    uiwait(msgbox('You''re done! Let the experimenter know'))
    if get(S.tt(2),'val') && S.audinfo.emoindsorted(S.keypresscount)~=str2double(S.caller(3))%Training mode&wrong answer

    %do nothing (Takes care of the rare case in training mode when the last
    %question is answered incorrectly and the program runs into trouble
    else    
    set(S.fh2,'visible','off')
    % 	disp('Thanks for participating')
    % % reportstuff('')
    %     S.txtinfo(4)=text('parent',S.axinfo,...
    %         'fontunits','normalized',...
    %         'units','normalized',...
    %         'fontsize',.07,...
    %         'fontw','bold',...
    %         'color',[.0 0 .2],...
    %         'position',[.02 .6 0],...
    %         'horizontalalignment','left',...
    %         'string',['Start time:          ',datestr(clock)]);
    uiwait(msgbox('The test is over. Please inform the experimenter.'))
    savestate(4,[],S)
%     set(S.fh3,'visible','on')
    %     set(S.fh2,'visible','off')
    end
    
end
% end

% allvars=S;
% if S.keypresscount==S.audinfo.wav  %Finishing the test
% disp('Thanks for participating')
% % reportstuff('')
% uiwait(msgbox('The test is over, thanks for your participation.'))
% delete(S.fh2)
% end
% if S.keypresscount==S.audinfo.wav %last question
% %    uiwait(msgbox('You''re done! Let the experimenter know'))
%    disp('Thanks for participating')
% % % reportstuff('')
% uiwait(msgbox('The test is over, thanks for your participation.'))
% delete(S.fh2)
%    set(S.fh3,'visible','on')
% end



% set(,'call',{@(pb_5emotions_call,S})
% % set(S{1,3}.keyspressed,'val',{proceed,S})

% % Callback for pushbutton, deletes one line from listbox.
% S = varargin{3};  % Get the structure.
% % SSS=varargin;
% L = get(S.ls,{'string','value'});  % Get the users choice.
%
% % We need to make sure we don't try to assign an empty string.
% if ~isempty(L{1})
%     L{1}(L{2}(:)) = [];  % Delete the selected strings.
% end
%
% if min(L{2})>1
%     set(S.ls,'string',L{1},'val',min(L{2})-1) % Set the new string to the previous.
% else
%     set(S.ls,'string',L{1},'val',1) % Set the new string to the first in list.
% end

% save('varibls','SSS')
