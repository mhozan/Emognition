function [] = savestate(varargin)
%SAVESTATE Summary of this function goes here
%   Detailed explanation goes here
% v2.1 update: replaced deprecated 'xlswrite' by writecell & writematrix

S=varargin{1,3};
a=get(S.fh3,'visible');
set(S.fh3,'visible','off')
formatOut = 'yyyymmdd_HHMMSS';
S.dateandtime=datestr(datetime('now'),formatOut);
unitz=S.fh3.Units;  %temporarily saves figure positions to restore them after printing the pdf
positz=S.fh3.Position; %temporarily saves figure positions to restore them after printing the pdf
set(S.fh3,'PaperOrientation','landscape',...  Optimize figure for printing as PDF
    'PaperType','usletter',...
    'Units','inches',...
    'Position',[0 .5 11 8],...
    'PaperPositionMode','manual',...
    'PaperPosition',[0 .5 11 8]);
w8msg='Generating Reports...';
w8ttl='Saving...';
% h = waitbar(0/10);

S.PDF='';
S.XLS='';

chc1='Show the report';
chc2='Return to the main window';
if S.keypresscount==S.wavs && ~S.tt(2).Value
    S.correct=S.keyspressed==S.audinfo.emoindsorted; %compares pressed keys and played sequence for the correct answers
end

% warning off
if varargin{1,1}==1 && ~get(S.tt(2),'val')
    %     if get(S.ch(8),'val')
    %     save([S.ed(3).String,'\',S.ed(1).String,'_',S.dateandtime,'_closerequstsave','.mat'],...
    %         '-STRUCT','S','keyspressed','keypresscount','audiosshuffled',...
    %         'dateandtime','ed','audir','bgdir',...
    %         'instants','Reactimez','confuble','tabl','percentabl','audinfo','txtinfo')
    %     end
    h=waitbar(1/10,w8msg,'name',w8ttl);

    save([S.ed(3).String,'\',S.ed(1).String,'_',S.dateandtime,S.audinfo.audiofoldername,'_closereq2','.mo3n'],...
        '-STRUCT','S')
    %     if S.ch(6).Value
    %     print(S.fh3,'-dpdf',[S.ed(3).String,'\',S.ed(1).String,'_',S.dateandtime,'_closerequstsave'])
    %     end
    waitbar(10/10);
    close(h)
    disp(['Progress succesfully saved in ',S.ed(3).String])
    %     uiwait(msgbox(['Progress successfully saved in: ',S.ed(3).String]))
    
    %     choice = questdlg(['Progress was successfully saved in: ',S.ed(3).String],...
    %         'RESULTS SAVED','Exit the program',chc2,chc2);
    uiwait(msgbox(['Progress is succesfully saved in ',S.ed(3).String,'\']))
    set(S.fh,'visible','on')
    %     switch choice
    %         case 'Exit the program'
    %             try delete(S.fh3); catch; end
    %             try delete(S.fh2); catch; end
    %             delete(S.fh)%             set(S.fh3,'visible','on')
    %         case chc2
    %             set(S.fh,'visible','on')
    %         otherwise %closed the confirmation dialogue?
    %             disp('questionnotansweredin savestate.m')
    %             set(S.fh,'visible','on')
    %     end
    %
    
    
    %     winopen([S.ed(3).String,'\',S.ed(1).String,'_',S.dateandtime,'_closerequstsave','.pdf'])
    
elseif varargin{1,1}==2 && ~get(S.tt(2),'val')
    %     save([S.ed(3).String,'\',S.ed(1).String,'_',S.dateandtime,'_unexpected1error','.mat'],...
    %         '-STRUCT','S','keyspressed','keypresscount','audiosshuffled',...
    %         'dateandtime','ed','audir','bgdir',...
    %         'instants','Reactimez','confuble','tabl','percentabl','audinfo','txtinfo')
    h=waitbar(1/10,w8msg,'name',w8ttl);
    save([S.ed(3).String,'\',S.ed(1).String,'_',S.dateandtime,S.audinfo.audiofoldername,'_closereq','.mo3n'],...
        '-STRUCT','S')
    %     if S.ch(6).Value
    %     print(S.fh3,'-dpdf',[S.ed(3).String,'\',S.ed(1).String,'_',S.dateandtime,'_unexpected1error'])
    % end
    disp(['Unexpected Error! Progress succesfully saved in ',S.ed(3).String])
    waitbar(10/10);
    close(h)    
    %     uiwait(msgbox(['Unexpected Error! Progress successfully saved in: ',S.ed(3).String]))
    choice = questdlg(['Results are successfully saved in: ',S.ed(3).String],...
        'Unexpected Error!',chc1,chc2,chc2);
    
    switch choice
        case chc1
            set(S.fh3,'visible','on')
        case chc2
            set(S.fh,'visible','on')
            set(S.fh3,'visible','off')
            
        otherwise %closed the confirmation dialogue?
            disp('questionnotansweredin savestate.m')
            set(S.fh,'visible','on')
    end
    %     winopen([S.ed(3).String,'\',S.ed(1).String,'_',S.dateandtime,'_unexpected1error','.pdf'])
    
elseif varargin{1,1}==3 && ~get(S.tt(2),'val')
    %     save([S.ed(3).String,'\',S.ed(1).String,'_',S.dateandtime,'_manualsave','.mat'],...
    %         '-STRUCT','S','keyspressed','keypresscount','audiosshuffled',...
    %         'dateandtime','ed','audir','bgdir',...
    %         'instants','Reactimez','confuble','tabl','percentabl','audinfo','txtinfo')
    h=waitbar(1/10,w8msg,'name',w8ttl);
    save([S.ed(3).String,'\',S.ed(1).String,'_',S.dateandtime,S.audinfo.audiofoldername,'_manualsave','.mo3n'],...
        '-STRUCT','S')
    %     S.XLS=[S.ed(3).String,'\',S.ed(1).String,'_',S.dateandtime,S.audinfo.audiofoldername,'_manualsave'];
    if S.ch(6).Value
        waitbar(5/10);
        S.PDF=[S.ed(3).String,'\',S.ed(1).String,'_',S.dateandtime,S.audinfo.audiofoldername,'_manualsave'];
        print(S.fh3,'-dpdf',S.PDF)
        S.PDF=[S.PDF,'.pdf'];
    end
    disp(['Progress succesfully saved in ',S.ed(3).String])
    waitbar(10/10);
    close(h)
    %     uiwait(msgbox(['Progress successfully saved in: ',S.ed(3).String]))
    choice = questdlg(['Results are successfully saved in: ',S.ed(3).String],...
        'RESULTS SAVED',chc1,chc2,chc2);
    %     assignin('base','S',S)
    switch choice
        case chc1
            if S.ch(6).Value
                fileloc=['View',' <a href="',S.PDF,'">PDF</a> Report.'];
                disp(fileloc)
                %                 text('parent',S.axinfo,...
                %                     'fontunits','normalized',...
                %                     'units','normalized',...
                %                     'fontsize',.04,...
                %                     'fontw','bold',...
                %                     'color',[.0 0 1],...
                %                     'position',[.02 .1 0],...
                %                     'horizontalalignment','left',...
                %                     'string',['View PDF: ...',S.PDF(max(1,end-70):end),'.pdf']);
            end
%             if S.ch(7).Value
%                 fileloc=['View',' <a href="',S.PDF,'.xls','">Excel</a> Report.'];
%                 disp(fileloc)
%             end
            set(S.fh3,'visible','on')
        case chc2
            set(S.fh,'visible','on')
            set(S.fh3,'visible','off')
            
        otherwise %closed the confirmation dialogue?
            disp('questionnotansweredin savestate.m')
            set(S.fh,'visible','on')
    end
    %     winopen([S.ed(3).String,'\',S.ed(1).String,'_',S.dateandtime,'_manualsave','.pdf'])
    
elseif varargin{1,1}==4 %&& ~get(S.tt(2),'val')
    h=waitbar(1/10,w8msg,'name',w8ttl);
    if get(S.ch(8),'val')
        S.Reactimez=real(reactiontime(S.instants));
        S.shuffledaudios=squeeze(S.audiosshuffled{1,1}');
        save([S.ed(3).String,'\',S.ed(1).String,'_',S.dateandtime,S.audinfo.audiofoldername,'_test','.mat'],...
            '-STRUCT','S','keyspressed','keypresscount','shuffledaudios',...
            'dateandtime','ed','audir','bgdir',...
            'instants','Reactimez','confuble','tabl','percentabl','audinfo','txtinfo')
    end
    %     save([S.ed(3).String,'\',S.ed(1).String,'_',S.dateandtime,'_test','.mo3n'],...
    %         '-STRUCT','S')
    %     S.PDF=[S.ed(3).String,'\',S.ed(1).String,'_',S.dateandtime,S.audinfo.audiofoldername,'_test'];
    if S.ch(6).Value
        S.PDF=[S.ed(3).String,'\',S.ed(1).String,'_',S.dateandtime,S.audinfo.audiofoldername,'_test'];
        print(S.fh3,'-dpdf',S.PDF)
        S.PDF=[S.PDF,'.pdf'];
        waitbar(2/10);
    end
    %     warning off
    if S.ch(7).Value %Generate Excel Report?
        try  %writing info to an excel spreadsheet
        	S.XLS=[S.ed(3).String,'\',S.ed(1).String,'_',S.dateandtime,S.audinfo.audiofoldername,'_test','.xlsx'];
            %% confusion matrix sheet
            writematrix(S.tabl.Data,...
                S.XLS,'Sheet','Confusion Matrix','Range','B2:F6'); waitbar(2/10);
            writecell(S.confuble.XTickLabel',...
                S.XLS,'Sheet','Confusion Matrix','Range','B1:F1'); waitbar(3/10);
            writecell(S.confuble.XTickLabel,...
                S.XLS,'Sheet','Confusion Matrix','Range','A2:A6'); waitbar(4/10);            
            %% percentages sheet
            writematrix(S.percentabl.Data,...
                S.XLS,'Sheet','Percentages','Range','B2'); waitbar(5/10);
            writecell({'happy';'scared';'neutral';'sad';'angry';'female';'male';'Total'},...
                S.XLS,'Sheet','Percentages','Range','A2'); waitbar(6/10);
        	writecell({'% Correct','Avg. Reaction(S)','Avg. Replays'},...
                S.XLS,'Sheet','Percentages','Range','B1'); waitbar(7/10);
            
            %% pressed keys sheet        

          	writecell(S.audiosshuffled{1,1}',...
                S.XLS,'Sheet','Pressed Keys','Range','A2'); waitbar(8/10);
            writematrix(S.correct,...
                S.XLS,'Sheet','Pressed Keys','Range','B2'); waitbar(8.5/10);            
            writematrix(S.audinfo.emoindsorted,...
                S.XLS,'Sheet','Pressed Keys','Range','C2'); waitbar(8.75/10);
            writematrix(S.keyspressed,...
                S.XLS,'Sheet','Pressed Keys','Range','D2'); waitbar(9/10);            
          	writecell({'1: Happy';'2: Scared'; '3: Neutral'; '4: Sad'; '5: Angry'},...
                S.XLS,'Sheet','Pressed Keys','Range','H2'); waitbar(9.25/10);            
            writematrix(real(reactiontime(S.instants)),...
                S.XLS,'Sheet','Pressed Keys','Range','E2');  
        	writecell({'Audio filename','Correct Answer?','Played Sequence','Pressed Keys','Reaction Times(S)','Replays?'},...
                S.XLS,'Sheet','Pressed Keys','Range','A1:F1'); waitbar(9.5/10);            

        catch err
            disp(err)
        end
    end
    %     warning on
    disp(['Results succesfully saved in ',S.ed(3).String])
    waitbar(10/10);
    close(h)
    %     uiwait(msgbox(['Results successfully saved in: ',S.ed(3).String]))
    choice = questdlg(['Results are successfully saved in: ',S.ed(3).String],...
        'RESULTS SAVED',chc1,chc2,chc2);
    
    switch choice
        case chc1
            if S.ch(6).Value
                
                fileloc=['View',' <a href="',S.PDF,'">PDF</a> Report.'];
                disp(fileloc)
            end
            if S.ch(7).Value
                fileloc=['View',' <a href="',S.XLS,'">Excel</a> Report.'];
                disp(fileloc)
            end
            set(S.fh3,'visible','on')
        case chc2
            set(S.fh,'visible','on')
            set(S.fh3,'visible','off')
            
        otherwise %closed the confirmation dialogue?
            disp('questionnotansweredin savestate.m')
            set(S.fh,'visible','on')
    end
    %     winopen([S.ed(3).String,'\',S.ed(1).String,'_',S.dateandtime,'_test','.pdf'])
elseif  get(S.tt(2),'val')    %training mode
    h=waitbar(1/10,w8msg,'name',w8ttl);
    if S.ch(6).Value
        S.PDF=[S.ed(3).String,'\',S.ed(1).String,'_',S.dateandtime,S.audinfo.audiofoldername,'_training'];
        print(S.fh3,'-dpdf',S.PDF)        
        S.PDF=[S.PDF,'.pdf'];
        waitbar(2/10);
    end
    %     uiwait(msgbox('Done with the training... Please inform the experimenter.'))
    if S.ch(7).Value %Generate Excel Report?
        try  %writing info to an excel spreadsheet
        	S.XLS=[S.ed(3).String,'\',S.ed(1).String,'_',S.dateandtime,S.audinfo.audiofoldername,'_training','.xlsx'];
            %% confusion matrix sheet
            writecell(S.confuble.XTickLabel',...
                S.XLS,'Sheet','Confusion Matrix','Range','B1:F1'); waitbar(2/10);
            writecell(S.confuble.XTickLabel,...
                S.XLS,'Sheet','Confusion Matrix','Range','A2:A6'); waitbar(3/10);
            writematrix(S.tabl.Data,...
                S.XLS,'Sheet','Confusion Matrix','Range','B2:F6'); waitbar(4/10);
            
            %% percentages sheet
            writematrix(S.percentabl.Data,...
                S.XLS,'Sheet','Percentages','Range','B2'); waitbar(5/10);
            writecell({'happy';'scared';'neutral';'sad';'angry';'female';'male';'Total'},...
                S.XLS,'Sheet','Percentages','Range','A2'); waitbar(6/10);
        	writecell({'% Correct','Avg. Reaction(S)','Avg. Replays'},...
                S.XLS,'Sheet','Percentages','Range','B1'); waitbar(7/10);
            
            %% pressed keys sheet        
        	writecell({'Audio filename','Correct Answer?','Played Sequence','Pressed Keys','Reaction Times(S)','Replays?'},...
                S.XLS,'Sheet','Pressed Keys','Range','A1:F1'); waitbar(7.5/10);
          	writecell(S.audiosshuffled{1,1}',...
                S.XLS,'Sheet','Pressed Keys','Range','A2'); waitbar(8/10);
            writematrix(S.correct,...
                S.XLS,'Sheet','Pressed Keys','Range','B2'); waitbar(8.5/10);            
            writematrix(S.audinfo.emoindsorted,...
                S.XLS,'Sheet','Pressed Keys','Range','C2'); waitbar(8.75/10);
            writematrix(S.keyspressed,...
                S.XLS,'Sheet','Pressed Keys','Range','D2'); waitbar(9/10);            
            writematrix(real(reactiontime(S.instants)),...
                S.XLS,'Sheet','Pressed Keys','Range','E2'); waitbar(9.5/10);  
            writecell({'1: Happy';'2: Scared'; '3: Neutral'; '4: Sad'; '5: Angry'},...
                S.XLS,'Sheet','Pressed Keys','Range','H2'); waitbar(9.25/10);                      

        catch err
            disp(err)
        end
    end
    waitbar(10/10);
    close(h)
    choice = questdlg(['Training reports successfully saved in: ',S.ed(3).String],...
        'RESULTS SAVED',chc1,chc2,chc2);
    
    switch choice
        case chc1
            set(S.fh3,'visible','on')
        case chc2
            
            set(S.fh,'visible','on')
            set(S.fh3,'visible','off')
        otherwise %closed the confirmation dialogue?
            disp('questionnotansweredin savestate.m')
            set(S.fh,'visible','on')
    end
else
    %     save([S.ed(3).String,'\',S.ed(1).String,'_',S.dateandtime,'_unexpected2error','.mat'],...
    %         '-STRUCT','S','keyspressed','keypresscount','audiosshuffled',...
    %         'dateandtime','ed','audir','bgdir',...
    %         'instants','Reactimez','confuble','tabl','percentabl','audinfo','txtinfo')
    h=waitbar(1/10,w8msg,'name',w8ttl);
    save([S.ed(3).String,'\',S.ed(1).String,'_',S.dateandtime,S.audinfo.audiofoldername,'_unexpected2error','.mo3n'],'-STRUCT','S')
    %     if S.ch(6).Value
    %         print(S.fh3,'-dpdf',[S.ed(3).String,'\',S.ed(1).String,'_',S.dateandtime,'_unexpected2error'])
    %     end
    % writetable(S.tabl.Data,'myData.xls')

    waitbar(10/10);
    close(h)
    disp(['Unexpected error! Progress succesfully saved in ',S.ed(3).String])
    %     uiwait(msgbox(['Progress successfully saved in: ',S.ed(3).String]))
    choice = questdlg(['Results are successfully saved in: ',S.ed(3).String],...
        'Unexpected error!',chc1,chc2,chc2);
    
    switch choice
        case chc1
            set(S.fh3,'visible','on')
        case chc2
            set(S.fh,'visible','on')
            set(S.fh3,'visible','off')
        otherwise %closed the confirmation dialogue?
            disp('questionnotansweredin savestate.m')
            set(S.fh,'visible','on')
    end
    % 	winopen([S.ed(3).String,'\',S.ed(1).String,'_',S.dateandtime,'_unexpected2error','.pdf'])
    
    
end

% try close(h); catch; end;


if strcmp(a,'on')
    set(S.fh3,'visible','on')
end
if S.ch(6).Value
    uicontrol(S.fh3,'style','push',...'parent',S.axinfo,...
        'fontunits','normalized',...
        'units','normalized',...
        'fontsize',.4,...
        'fontw','bold',...
        'foregroundcolor',[.0 0 1],...
        'position',[.1 .6 .1 .03],...
        'horizontalalignment','left',...
        'string','View PDF Report',...
        'tooltipstring',S.PDF',...
        'call',{@viwfil,S.PDF});%'call',{@viwfil,S.ed(3).String});
end
if S.ch(7).Value
    uicontrol(S.fh3,'style','push',...'parent',S.axinfo,...
        'fontunits','normalized',...
        'units','normalized',...
        'fontsize',.4,...
        'fontw','bold',...
        'foregroundcolor',[.0 0 1],...
        'position',[.21 .6 .1 .03],...
        'horizontalalignment','left',...
        'string','View Excel Report',...
        'tooltipstring',S.XLS',...
        'call',{@viwfil,S.XLS});...'call',{@viwfil,S.ed(3).String});
end
uicontrol(S.fh3,'style','push',...'parent',S.axinfo,...
    'fontunits','normalized',...
    'units','normalized',...
    'fontsize',.4,...
    'fontw','bold',...
    'foregroundcolor',[.0 0 1],...
    'position',[.32 .6 .2 .03],...
    'horizontalalignment','left',...
    'string','Locate Audio Input Folder',...
    'tooltipstring',S.ed(4).String',...
    'call',{@viwfil,S.ed(4).String});
set(S.fh3,'Units',unitz,...
    'Position',positz);

function viwfil(varargin)
dr=varargin{1,3};
try
    [status,~]=system(['explorer.exe ',dr]);

catch err
    errordlg(err,['Access Error: ',num2str(status)])
end

