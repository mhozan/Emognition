function []=rusure(varargin)
% main gui close statement
% a=varargin;

S=varargin{1,3};
% if S.keypresscount>5   % Are we progressed far enough the data is worth saving?
if S.keypresscount<1
    disp('closed too early to be worth saving! ')
    %         delete(S.fh2) %Closes figures
    %         delete(S.fh)
    %
    %         if isfield(S,'fh3')
    %             delete(S.fh3)
    %         end
    try delete(S.fh2); catch; end
    try delete(S.fh3); catch; end
    set(S.fh,'visible','on')
    return
    %         close all force
elseif S.keypresscount==S.audinfo.wav
    disp('data already saved.')
    try delete(S.fh2); catch; end
    try delete(S.fh3); catch; end
    set(S.fh,'visible','on')
    return
    %     close all force
else
    try
        choice = questdlg(['Do you want to save the progress for "',S.ed(1).String,'" ?'], ...
            'Emotion Recognition Test v2.0', ...
            'Save','Don''t Save','Cancel','Cancel');
        
        % Handle response
        switch choice
            case 'Save'
                try savestate(1,[],S)
                    
                    delete(S.fh2) %Closes figures
                    %             delete(S.fh)
                    set(S.fh,'visible','on')
                    
                    %         if ~isempty(S.fh3)
                    delete(S.fh3)
                    return
                    %         end
                    
                catch err
                    disp(err)
                    disp(['Could not save the progress in ',S.ed(3).String,'\'])
%                     uiwait(msgbox(['Could NOT save the progress in ',S.ed(3).String,'\'],'UNEXPECTED ERROR #46','error'))
                    delete(S.fh2) %Closes figures
                    set(S.fh,'visible','on')
                    delete(S.fh3)
                    return
                end
            case 'Don''t Save'
                disp('Data not saved')
                delete(S.fh2) %Closes figures
                %         delete(S.fh)
                set(S.fh,'visible','on')
                
                %         if isfield(S,'fh3')
                delete(S.fh3)
                return
                %         end
            case 'Cancel'
                %Do nothing
                disp('returned to the task')
                return%was here
            otherwise %save anyway
                try savestate(2,[],S)
                catch
                end
                if isfield(S,'fh2')
                    delete(S.fh2) %Closes figures
                end
                if isfield(S,'fh')
                    msgbox('unexpected error 01146')
                    delete(S.fh)
                end
                if isfield(S,'fh3')
                    delete(S.fh3)
                end
                return
        end
        
    catch err
        disp(err)
        uiwait(msgbox('Unexpected Error! The program will shut down','ERROR 2246','error'))
        close all force
        return
    end
end
% else
%     try delete(S.fh2); %Closes figures
%         delete(S.fh)
%     catch err
%         disp(err)
%     end



%
% uiwait(msgbox('see you soon'))
% delete(S.fh2)
% delete(S.fh)




