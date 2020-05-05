function []=buttonrelocate(varargin)
%gets called by proceed.m if S.emo.Value has less than 5 emotions
S=varargin{1,3};
%pbe1:   'position',[.85 .81 .10 .10*S.screen.ratio],...  keeps it in square shape
%pbe2    'position',[.85 .61 .10 .10*S.screen.ratio],...
%pbe3    'position',[.85 .41 .10 .10*S.screen.ratio],...
%pbe4    'position',[.85 .21 .10 .10*S.screen.ratio],...
%pbe5    'position',[.85 .01 .10 .10*S.screen.ratio],...
% assignin('base','Sbut',S)



% S.emonum=sum(cell2mat(get(S.emo,'value')));
S.emoz=cell2mat(get(S.emo,'Value'));
disp('buttons relocated.')
buttonz=find(S.emoz);
switch sum(S.emoz)
    case 2
        set(S.pbe(buttonz(1)),'Position',[.85 .61 .10 .10*S.screen.ratio])
        set(S.pbe(buttonz(2)),'Position',[.85 .21 .10 .10*S.screen.ratio])        
    case 3
        set(S.pbe(buttonz(1)),'Position',[.85 .71 .10 .10*S.screen.ratio])
        set(S.pbe(buttonz(2)),'Position',[.85 .41 .10 .10*S.screen.ratio])           
        set(S.pbe(buttonz(3)),'Position',[.85 .11 .10 .10*S.screen.ratio])    
    case 4
        set(S.pbe(buttonz(1)),'Position',[.85 .71 .10 .10*S.screen.ratio])
        set(S.pbe(buttonz(2)),'Position',[.85 .51 .10 .10*S.screen.ratio])           
        set(S.pbe(buttonz(3)),'Position',[.85 .31 .10 .10*S.screen.ratio])
        set(S.pbe(buttonz(4)),'Position',[.85 .11 .10 .10*S.screen.ratio])        
        
    otherwise 
        disp('we should not get here in buttonrelocate.m')
        
end






%
% S.confuble.Visible='on';
% S.percentabl.Visible='on';