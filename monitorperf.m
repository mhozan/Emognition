function [] = monitorperf(varargin)
%MONITORPERF shows real time performance of the user in a separate window
% gets normally called by pb_5emotions, extraclick.m, or occasionally by
% pb_pauser.m or S.replayer pushbutton through moh3nplayer.m
% Figure is defined in preproceed.m
% -9998 Resume
% -9999 Pause
% -1009 Replay
% -1001 Clicks
% -1002 Stops
% -1008 Replay2/Stop2: Special case when replays are not allowed except after
% resuming from a pause


% 1 Happy
% 2 Scared
% 3 Neutral
% 4 Sad
% 5 Angry
S=varargin{1,3};

% if get(S.ch(4),'val')  %monitor performance? make it visible
%     set(S.fh3,'visible','on')
% else
%     set(S.fh3,'visible','off')
% end

% assignin('base','S',S);

if isfield(S,'fh3') && ...
        ~isempty(S.audinfo.emoindsorted) && ...
        ~isempty(S.keyspressed)% &&...
    %         length(Sm.keyspressed)==length(Sm.audinfo.emoindsorted)
    %     if S.keyspressed(end)==S.audinfo.emoindsorted(end)  %the right button is pressed!
    %         S.tabl.Data(S.keyspressed(end),S.keyspressed(end))=...  %diagonal elemnts
    %             S.tabl.Data(S.keyspressed(end),S.keyspressed(end))+1;
    %     elseif S.keyspressed(end)~=S.audinfo.emoindsorted(end)

    
    S.tabl.Data(S.audinfo.emoindsorted(S.keypresscount),S.keyspressed(end))=...
        S.tabl.Data(S.audinfo.emoindsorted(S.keypresscount),S.keyspressed(end))+1;  %updates the table
    
    
    % correct answers or not
    %     S.audinfo.correct(S.keypresscount)=S.keyspressed(end)==S.audinfo.emoindsorted(S.keypresscount);
    
    %% update percent corrects
    
    S.percentabl.Data(1,1)=100*(S.tabl.Data(1,1))/sum(S.tabl.Data(1,:));
    S.percentabl.Data(2,1)=100*(S.tabl.Data(2,2))/sum(S.tabl.Data(2,:));
    S.percentabl.Data(3,1)=100*(S.tabl.Data(3,3))/sum(S.tabl.Data(3,:));
    S.percentabl.Data(4,1)=100*(S.tabl.Data(4,4))/sum(S.tabl.Data(4,:));
    S.percentabl.Data(5,1)=100*(S.tabl.Data(5,5))/sum(S.tabl.Data(5,:));
    %     S.percentabl.Data(6)=100*trace(S.tabl.Data)/S.keypresscount; %total percent correct (sum of diagonal elements)
    
    %     S.percentabl.Data(6,1)=-1;%100*trace(S.tabl.Data)/sum(S.tabl.Data(:)); %Female percent correct (sum of diagonal elements)
    %     S.percentabl.Data(7,1)=-2;%100*trace(S.tabl.Data)/sum(S.tabl.Data(:)); %Male percent correct (sum of diagonal elements)
    S.percentabl.Data(8,1)=100*trace(S.tabl.Data)/sum(S.tabl.Data(:)); %total percent correct (sum of diagonal elements)
    
    
    %%
	Clim=[-1,S.audinfo.wav/sum(cell2mat({S.emo.Value}))];
	
%     if S.ch(4).Value    
% 	axes(S.confuble)  %confusion table visualization 
    %Feb 2020: axes command overwrites the visibility of the parent
    %figure! issue discussed here: https://www.mathworks.com/matlabcentral/answers/155250-figure-visibility-changes-upon-axes-call
%     S.fh3.CurrentAxes = S.confuble;
  
        %     Clim=[0,S.audinfo.wav/5];
        %     Cmap=[]
    imagesc(S.confuble,S.tabl.Data,Clim), colormap(S.confuble,'gray'), axis(S.confuble,'image')

%     end
    %     colormap(flipud(colormap))%inverts the colormap
    S.confuble.XTick=1:5;
    S.confuble.YTick=1:5;
    S.confuble.XTickLabel = {'Happy','Scared','Neutral','Sad','Angry'};
    S.confuble.XAxisLocation='top';
    S.confuble.XTickLabelRotation=45;
    S.confuble.YTickLabelRotation=45;
    S.confuble.YTickLabel = {'Happy','Scared','Neutral','Sad','Angry'};
    for i=1:5
        for j=1:5
            if S.tabl.Data(5+1-i,5+1-j) %only put values
                textcol=[.9 .1 .1];
                %                 try textcol=[1-S.tabl.Data(5+1-i,5+1-j)/(S.audinfo.wav/5),...r
                %                     1-S.tabl.Data(5+1-i,5+1-j)/(S.audinfo.wav/5),...g
                %                     1-S.tabl.Data(5+1-i,5+1-j)/(S.audinfo.wav/5)];%b
                %                 catch
                %                     textcol=[0 0 0];
                %                 end
            else
                textcol=[.6 .6 .6];
            end
            text(S.confuble,5+1-j,5+1-i,num2str(S.tabl.Data(5+1-i,5+1-j)),...
                'HorizontalAlignment','center',...
                'color',textcol)
        end
    end
    drawnow
    
    %% reactiontime
    
    %     if exist('Clicks','var') && exist('Stops','var') && numel(Clicks)==numel(Stops)
    %
    %         if ~exist('Replays','var') && ~exist('Pauses','var') && ~exist('Resumes','var')
    %
    % %             if
    %                 Reactimez(S.keypresscount)=...
    %                     etime(Clicks(S.keypresscount,2:7),Stops(S.keypresscount,2:7));
    %                 assignin('base','Reactimez',Reactimez);
    % %             end
    %
    %         end
    %     end
    %     x1=S.instants;
    %     x2=x1;
    %     x2(x2==-1008)=-1002.1; %replcae with stop tags
    S.Reactimez=real(reactiontime(S.instants));
    
    if S.Reactimez==0
        %do nothing
    else
        %         assignin('base','S',S);
        
        %         if length(S.keyspressed)==S.keypresscount;
        S.correctZ=S.keyspressed(1:S.keypresscount)==S.audinfo.emoindsorted(1:S.keypresscount); %compares pressed keys and played sequence for the correct answers
        %         else
        %             S.correctZ=zeros(1,S.keypresscount);
        %         end
        pcf=100*sum(S.femindz(1:S.keypresscount).*S.correctZ)/sum(S.femindz(1:S.keypresscount)); %percent correct female
        pcm=100*sum(S.malindz(1:S.keypresscount).*S.correctZ)/sum(S.malindz(1:S.keypresscount));%percent correct male
        
        reactf=S.femindz(1:S.keypresscount).*S.Reactimez(:,1);  %reactions female
        reactf=mean(reactf(reactf>0)); %exclude zeros in average
        
        reactm=S.malindz(1:S.keypresscount).*S.Reactimez(:,1); %reactions male
        reactm=mean(reactm(reactm>0)); %exclude zeros in average
        
        repf=S.femindz(1:S.keypresscount).*S.Reactimez(:,2);  %replays female
        repf=sum(repf)/sum(S.femindz(1:S.keypresscount));
        
        repm=S.malindz(1:S.keypresscount).*S.Reactimez(:,2);  %replays male
        repm=sum(repm)/sum(S.malindz(1:S.keypresscount));
        
        S.percentabl.Data(6,1)=pcf;%100*trace(S.tabl.Data)/sum(S.tabl.Data(:)); %Female percent correct (sum of diagonal elements)
        S.percentabl.Data(7,1)=pcm;%100*trace(S.tabl.Data)/sum(S.tabl.Data(:)); %Male percent correct (sum of diagonal elements)
        
        
        S.percentabl.Data(1,2)= mean(S.Reactimez(S.audinfo.hapindsorted(S.audinfo.hapindsorted<=S.keypresscount),1));
        S.percentabl.Data(2,2)= mean(S.Reactimez(S.audinfo.scaindsorted(S.audinfo.scaindsorted<=S.keypresscount),1));
        S.percentabl.Data(3,2)= mean(S.Reactimez(S.audinfo.neuindsorted(S.audinfo.neuindsorted<=S.keypresscount),1));
        S.percentabl.Data(4,2)= mean(S.Reactimez(S.audinfo.sadindsorted(S.audinfo.sadindsorted<=S.keypresscount),1));
        S.percentabl.Data(5,2)= mean(S.Reactimez(S.audinfo.angindsorted(S.audinfo.angindsorted<=S.keypresscount),1));
        S.percentabl.Data(6,2)= reactf;%mean(S.Reactimez(:,1));%avg. reaction time female
        S.percentabl.Data(7,2)= reactm;%mean(S.Reactimez(:,1));%avg. reaction time male
        S.percentabl.Data(8,2)= mean(S.Reactimez(:,1));%avg. reaction time total
        
        
        S.percentabl.Data(1,3)= mean(S.Reactimez(S.audinfo.hapindsorted(S.audinfo.hapindsorted<=S.keypresscount),2));
        S.percentabl.Data(2,3)= mean(S.Reactimez(S.audinfo.scaindsorted(S.audinfo.scaindsorted<=S.keypresscount),2));
        S.percentabl.Data(3,3)= mean(S.Reactimez(S.audinfo.neuindsorted(S.audinfo.neuindsorted<=S.keypresscount),2));
        S.percentabl.Data(4,3)= mean(S.Reactimez(S.audinfo.sadindsorted(S.audinfo.sadindsorted<=S.keypresscount),2));
        S.percentabl.Data(5,3)= mean(S.Reactimez(S.audinfo.angindsorted(S.audinfo.angindsorted<=S.keypresscount),2));
        S.percentabl.Data(6,3)= repf;%mean(S.Reactimez(:,2)); %avg replays female
        S.percentabl.Data(7,3)= repm;%;mean(S.Reactimez(:,2)); %avg replays male
        S.percentabl.Data(8,3)= mean(S.Reactimez(:,2)); %avg replays total
        
        
        circlearea=25*(real(S.Reactimez(:,2))+1);
        circlecolor=(real(S.Reactimez(:,2))+1)/5; %up to 4 replays get a distinct level of red color (dark red: zero replays, bright red: 4+ replays)
        circlecolor(circlecolor>1)=1;
%         axes(S.reactimes)
%         set(S.fh3,'CurrentAxes',S.reactimes)        
%         set(S.fh3,'Visible',S.ch(4).Value); drawnow    
        plot(S.reactimes,1:S.keypresscount,S.Reactimez(:,1),'-.b'), 
        hold(S.reactimes,'on')
        scatter(S.reactimes,1:S.keypresscount,S.Reactimez(:,1),circlearea,...%Reactimez(:,2):circles area: the bigger the more replays
            [circlecolor,zeros(size(circlecolor)),zeros(size(circlecolor))])  %circles color
        title(S.reactimes,'Reaction times')
        xlabel(S.reactimes,'Audio#')
        ylabel(S.reactimes,'Reaction(seconds)')
        %         xlim([1 S.audinfo.wav])
        xlim(S.reactimes,[.5 S.audinfo.wav+.5])
        
        ylim(S.reactimes,[0 max(2,1.02*max(S.Reactimez(:,1)))])
        %         xlim([1 120])
        hold(S.reactimes,'off')
        grid(S.reactimes,'on')
        set(S.fh3,'Visible',S.ch(4).Value); drawnow    
    end
    %% General Info
    %     S.axinfo = axes('parent',S.fh3,...
    %     'units','normalized',...
    %     'position',[0.1 0.6 .4 .3],...
    %     'XTick',[],'YTick',[],...
    %     'XTickLabel',[],'YTickLabel',[],...
    %     'TickDir','out');
    %
    %     S.txtinfo(1)=text('parent',S.axinfo,...
    %     'fontunits','normalized',...
    %     'units','normalized',...
    %     'fontsize',.05,...
    %     'fontw','bold',...
    %     'color',[.0 0 .2],...
    %     'position',[.02 .9 0],...
    %     'horizontalalignment','left',...
    %     'string',['Subject:  ',get(S.ed(1),'string')]);
    %
    %     S.txtinfo(2)=text('parent',S.axinfo,...
    %     'fontunits','normalized',...
    %     'units','normalized',...
    %     'fontsize',.05,...
    %     'fontw','bold',...
    %     'color',[.0 0 .2],...
    %     'position',[.02 .8 0],...
    %     'horizontalalignment','left',...
    %     'string',['Experimenter:  ',get(S.ed(2),'string')]);
    if S.keypresscount==1
        S.txtinfo(4)=text('parent',S.axinfo,...
            'fontunits','normalized',...
            'units','normalized',...
            'fontsize',.05,...
            'fontw','normal',...
            'color',[.0 0 .2],...
            'position',[.02 .6 0],...
            'horizontalalignment','left',...
            'string',['Start-Finish time:       ',datestr(S.pb_begin.UserData,'HH:MM:SS;   mmm dd, yyyy')]);
    end
    if S.keypresscount==S.audinfo.wav
        S.txtinfo(5)=text('parent',S.axinfo,...
            'fontunits','normalized',...
            'units','normalized',...
            'fontsize',.05,...
            'fontw','normal',...
            'color',[.0 0 .2],...
            'position',[.55 .6 0],...
            'horizontalalignment','left',...
            'string',['-     ',datestr(now,'HH:MM:SS;   mmm dd, yyyy')]);
        S.txtinfo(6)=text('parent',S.axinfo,...
            'fontunits','normalized',...
            'units','normalized',...
            'fontsize',.05,...
            'fontw','normal',...
            'color',[.0 0 .2],...
            'position',[.02 .5 0],...
            'horizontalalignment','left',...
            'string',['Test Duration:            ',...
            datestr(etime(clock,S.pb_begin.UserData)/24/3600, 'HH:MM:SS')]);
        str7=sprintf('RMS Variability:           ^+/_-%5.4g',S.audinfo.rms.variability);
        if S.ch(9).Value
            str7=strcat(str7,'% (stdev/mean)      (normalized amplitudes)');
        else
            str7=strcat(str7,'% (stdev/mean)');
        end
        S.txtinfo(7)=text('parent',S.axinfo,...
            'fontunits','normalized',...
            'units','normalized',...
            'fontsize',.05,...
            'fontw','normal',...
            'color',[.0 0 .2],...
            'position',[.02 .3 0],...
            'horizontalalignment','left',...
            'string',str7);
        
        
        if S.tt(2).Value && ~S.tt(3).Value
            %         str8=sprintf('Mistakes in Active Training Mode: %d out of %d possible',S.notrights,(5-1)*S.audinfo.wav);
            str8='';
        else
            str8='';
        end
        S.txtinfo(8)=text('parent',S.axinfo,...
            'fontunits','normalized',...
            'units','normalized',...
            'fontsize',.05,...
            'fontw','normal',...
            'color',[.0 0 .2],...
            'position',[.02 .2 0],...
            'horizontalalignment','left',...
            'string',str8);
        %         uicontrol('style','push',...'parent',S.axinfo,...
        %             'fontunits','normalized',...
        %             'units','normalized',...
        %             'fontsize',.4,...
        %             'fontw','bold',...
        %             'foregroundcolor',[.0 0 1],...
        %             'position',[.1 .6 .15 .03],...
        %             'horizontalalignment','left',...
        %             'string','Locate Saved Reports',...
        %             'call',{@viwfil,S.ed(3).String});
        %          uicontrol('style','push',...'parent',S.axinfo,...
        %             'fontunits','normalized',...
        %             'units','normalized',...
        %             'fontsize',.4,...
        %             'fontw','bold',...
        %             'foregroundcolor',[.0 0 1],...
        %             'position',[.3 .6 .2 .03],...
        %             'horizontalalignment','left',...
        %             'string','Locate Audio Files',...
        %             'call',{@viwfil,S.ed(4).String});
        
        % S.pb1(3)=uicontrol('style','push',...
        %     'units','normalized',...
        %     'position',[.905 .535 .09 .06],...
        %     'fontunits','normalized',...
        %     'BusyAction','cancel',...
        %     'Interruptible','off',...
        %     'fontsize',.4,...
        %     'tag','pb1_3',...
        %     'string','Browse...');
        
        str9=(['Audio input folder:     ...',S.audir(max(end-50,1):end)]);%S.audinfo.audiofoldername(2:end)]);
        S.txtinfo(9)=text('parent',S.axinfo,...
            'fontunits','normalized',...
            'units','normalized',...
            'fontsize',.05,...
            'fontw','normal',...
            'color',[.0 0 .2],...
            'position',[.02 .4 0],...
            'horizontalalignment','left',...
            'string',str9);
    end
    
    
    %%
    
    


    set(S.fh3,'Visible',S.ch(4).Value); drawnow  
    %     end
%     grid on
%     drawnow
    
    
    %
end
drawnow
set(S.fmenu2,'Label','Save','Callback','savestate(3,[],S)');
set(S.fh3,'closerequestfcn',{@rusure,S})
set(S.fh2,'closerequestfcn',{@rusure,S})
% assignin('base','S',S);



%
% if S.keypresscount>=S.audinfo.wav %last question
% %    uiwait(msgbox('You''re done! Let the experimenter know'))
% 	disp('Thanks for participating')
% % % reportstuff('')
%     uiwait(msgbox('The test is over, thanks for your participation.'))
%     savestate(4,[],S)
%     set(S.fh3,'visible','on')
%     set(S.fh2,'visible','off')
%
% end

% function viwfil(varargin)
%     dr=varargin{1,3};
%     dos(['explorer.exe ',dr]);





