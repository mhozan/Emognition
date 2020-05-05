function [] = bgchanger(varargin)
%gets called by extraclick.m or pb_beginner.m
%BGCHANGER will change the background of the main gui
%gets called by extraclick.m

S=varargin{1,3};
bgmap=[];
indx=1+ceil(S.keypresscount/S.intervl);
% indxcopy=indx;
while  indx > length(S.bgimagestruct)
    %     indx=1+floor(rand*(length(S.bgimagestruct)));  %show images randomly after the first iteration
    indx=indx-length(S.bgimagestruct); %restart showing backgrounds from the beginning
end
if S.keypresscount==0 %Got called by pb_beginner.m Begin_test
    if ~get(S.ch(5),'val') %check the value of the shuffle checkbox
        try
            [bg_image,bgmap]=imread([S.bgdir,'\',S.bgimagestruct(1).name]);
        catch err
            disp(err)
            bg_image=[0 0;0 0]; bgmap=[0 0 0];
            fprintf(['\nNext time, remove the broken image "',S.bgimagestruct(1).name,'" from the background pictures directoy\n'])
            
        end
    elseif get(S.ch(5),'val') %check the value of the shuffle checkbox
        try
            [bg_image,bgmap]=imread([S.bgdir,'\',S.picsshuffled{1,1}{1,1}]);
        catch err
            disp(err)
            bg_image=[0 0;0 0]; bgmap=[0 0 0];
            fprintf(['\nNext time, remove the broken image "',S.bgimagestruct(1).name,'" from the background pictures directoy\n'])
        end
        
    else
        disp('I have no idea what just happenned')
    end
    
    
%     axes(S.ax2)
    
    try
        %             axes(S.ax2)
        
        image(S.ax2,bg_image)
        if ~isempty(bgmap)
            colormap(S.ax2,bgmap)
        end
        set(S.ax2,'XTick',[],'YTick',[])
    catch err
        disp(err)
        disp('unknown image file in directory, bgchanger line 48')
        image(S.ax2,0)
        set(S.ax2,'XTick',[],'YTick',[])
    end
    
elseif round(S.keypresscount/S.intervl)==S.keypresscount/S.intervl
    
    if ~get(S.ch(5),'val') %check the value of the shuffle checkbox
        try
            [bg_image,bgmap]=imread([S.bgdir,'\',S.bgimagestruct(indx).name]);
        catch
            bg_image=[0 0;0 0]; bgmap=[0 0 0];
            disp(['Next time, remove the broken image "',S.bgimagestruct(indx).name,'" from the background pictures directoy'])
            
        end
    elseif get(S.ch(5),'val') %check the value of the shuffle checkbox
        try
            [bg_image,bgmap]=imread([S.bgdir,'\',S.picsshuffled{1,1}{1,indx}]);
        catch
            bg_image=[0 0;0 0];bgmap=[0 0 0];
            disp(['Next time, remove the broken image "',S.picsshuffled{1,1}{1,indx},'" from the background pictures directoy'])
        end
        
    else
        disp('I have no idea what just happenned')
    end
    
    
%     axes(S.ax2)
    
    try
        %             axes(S.ax2)
        
        image(S.ax2,bg_image)
        if ~isempty(bgmap)
            colormap(S.ax2,bgmap)
        end
        set(S.ax2,'XTick',[],'YTick',[])
    catch err
        disp(err)
        disp('unknown image file in directory')
        image(S.ax2,0)
        set(S.ax2,'XTick',[],'YTick',[])
    end
end
if S.tt(2).Value  %Training mode
%     axes(S.ax2)
    
    if ~S.tt(3).Value %not Passive mode
        text('parent',S.ax2,...
            'fontunits','normalized',...
            'units','normalized',...
            'fontsize',.06,...
            'fontw','bold',...
            'color',[.5 0 .5],...
            'position',[.02 .9 0],...
            'horizontalalignment','left',...
            'string','Active Training Mode');
        text('parent',S.ax2,...
            'fontunits','normalized',...
            'units','normalized',...
            'fontsize',.02,...
            'fontw','bold',...
            'color',[.5 0 .5],...
            'position',[.03 .85 0],...
            'horizontalalignment','left',...
            'string','Try until you get it right!');
    else
        text('parent',S.ax2,...
            'fontunits','normalized',...
            'units','normalized',...
            'fontsize',.06,...
            'fontw','bold',...
            'color',[.5 0 .5],...
            'position',[.02 .9 0],...
            'horizontalalignment','left',...
            'string','Passive Training Mode');
        text('parent',S.ax2,...
            'fontunits','normalized',...
            'units','normalized',...
            'fontsize',.02,...
            'fontw','bold',...
            'color',[.5 0 .5],...
            'position',[.03 .85 0],...
            'horizontalalignment','left',...
            'string','The correct answer will light up!');
    end
end

% a=S.keypresscount
% assignin('base','Sbgchanger',S);
improg=zeros(1,S.audinfo.wav);  %ProgressBar Image Structure
progstr=sprintf('Progress: %i/%i',S.keypresscount,S.audinfo.wav);

if S.keypresscount>=1  %
    improg(1:S.keypresscount)=1;
%     figure(S.fh2)
%     axes(S.progbar)
    % hold on
    imagesc(S.progbar,[0 S.audinfo.wav],[0],improg)
%     imagesc(S.progbar,improg)
	set(S.progbar,'XTick',[],'YTick',[],'Colormap',[1 1 1;0 1 0],'Visible','on',...
        'unit','normalized',...
        'position',[0.16 0.01 .686 .05])
%     set(S.progbar,'XTick',[],'YTick',[],'Colormap',[1 1 1;0 1 0])
%     set(S.progbar,'XTick',[],'YTick',[],colormap,[1 1 1;0 1 0])
    % colormap('gray')
    % colormap([0 0 0;1 1 1]) %BW colormap
%     colormap(S.progbar,[1 1 1;0 1 0]) %Green-White colormap
%     set(S.progbar,'XTick',[],'YTick',[],'Visible','on')
else
    % do nothing (only happens when bgchanger gets called by pb_beginner.m)
end
% uistack(S.progbar,'top')
% image(improg),
% S.txt2=
% axes(S.progbar)
S.txt2=text('parent',S.progbar,...  %for progress bar
    'fontunits','normalized',...
    'units','normalized',...
    'fontsize',.5,...
    'fontw','bold',...
    'color',[1 .4 .4],...
    'position',[0.5 0.2 0],...
    'horizontalalignment','center',...
    'verticalalignment','bottom',...
    'string',progstr,'visible','on');
% S.txt2.String = progstr;
drawnow
% text(S.progbar,...  %for progress bar
%     progstr,...
%     'fontunits','normalized',...
%     'units','normalized',...
%     'fontsize',.5,...
%     'fontw','bold',...
%     'color',[1 .4 .4],...
%     'position',[0.5 0.2 0],...
%     'horizontalalignment','center',...
%     'verticalalignment','bottom');
% allvars=S;


% %Wanna  shuffle pictures randomly?
% x={sedamiad.bgimagestruct.name};
% y=x(randperm(length(x)))
% bg_image=imread([S.bgdir,'\',y(indx)]);
% axes(S.ax2)
% image(bg_image)




