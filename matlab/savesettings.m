function savesettings(varargin)
X=varargin{1};
% assignin('base','X',X)

if exist('prevset.txt','file')
    fileattrib('prevset.txt','-h')
end
fileID=fopen('prevset.txt','wt');%open to write and overwrite

emo=get(X.emo,'value');
tt=get(X.tt,'value');
ed=get(X.ed,'string');
ch=get(X.ch,'value');
% fprintf(fileID,char(b))
for i=1:6
fprintf(fileID,'S.ed(%d).String=''%s'';\n',i,ed{i});
end
for i=1:5
fprintf(fileID,'S.emo(%d).Value=%d;\n',i,emo{i});
end
for i=1:4
fprintf(fileID,'S.tt(%d).Value=%d;\n',i,tt{i});
end
for i=1:9
fprintf(fileID,'S.ch(%d).Value=%d;\n',i,ch{i});
end


fclose(fileID);
fileattrib('prevset.txt','+h')

% fileattrib('prevset.txt','-h','','s') %hide the file