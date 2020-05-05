function [] = loadstate(varargin)
%LOADSTATE Summary of this function goes here
%   Detailed explanation goes here
fprintf('loading data...\n')
fh=gcf;
fullfile(varargin{1,3}.exefolder,'*.mo3n')
[FileName,PathName] = uigetfile({fullfile(varargin{1,3}.exefolder,'*.mo3n'),'Saved Sessions'},...
    'Load a previously incomplete session');
% [FileName,PathName] = uigetfile({'*.mo3n','Saved Sessions'},'Load a previously incomplete session');

if FileName~=0
copyfile([PathName,FileName],'tempfiletoload.mat')
    set(fh,'visible','off')

try load('tempfiletoload.mat')
    l=1;
catch err
    l=0;
    disp(err)
    fprintf('unable to load: %d \n',l)
end
if l~=0
    delete('tempfiletoload.mat')
end
    
    

else
    fprintf('No file selected\n')
    return
end

