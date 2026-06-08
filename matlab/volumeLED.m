function []=volumeLED(varargin)
S=varargin{1,nargin};

% volumeout=S.Userdata(S.CurrentSample);
% assignin('base','S',S); %just to see the  properties in workspace

y2=S.pobj.UserData.audio;

% figure(101), plot(1:100,1,'color',[y2(S.CurrentSample) 0 0])
% if volumeout==3
% figure(101), stem(1:100,1.01:0.01:2,'color',[0 y2(S.CurrentSample) 0],'linewidth',6)
% drwanow

% fprintf(' %g\n',y2(S.CurrentSample))
% figure(101), image([1,1]), colormap([0 y2(S.pobj.CurrentSample) 0])

set(S.led,'backgroundcolor',[0 y2(S.pobj.CurrentSample) 0]) %Green LED Volume indicator
% allvars=S;
% end