function []=pb_beginner(varargin)
S=varargin{1,3};
% S.starttime=[-321,clock];
% disp('Welcome')
% pause(1)
% set(S.pbe(:),'visible','on')
% if get(S.ch4,'val') %extra click check box
set(S.pb_extra,'visible','on')
% end
% if get(S.ch2,'value'),
% set(S.replayer,'visible','on')
% end
% if S.keypresscount >3
% set(S.pb_pause,'visible','on')
% end
set(S.pb_begin,'visible','off','UserData',clock)
set(S.pb_pause,'visible','on','enable','off')
set(S.progbar,'visible','on')
drawnow
bgchanger([],[],S)



