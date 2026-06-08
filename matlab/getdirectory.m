function [] = getdirectory(varargin)
% gets called by "Browse..." buttons in eMosen1
S=varargin{1,3};
actiondata=varargin{1,2};
caller=actiondata.Source.Tag; %Which Browse... button called?
% assignin('base','abbas',S); %just to see the  properties in workspace
switch caller
        case 'pb1_1'
            str='Saving Results';
            input_directory=uigetdir(S.ed(3).String,['Select the location for  ',str]);

        case 'pb1_2'
            str='.WAV audio files';
            input_directory=uigetdir(S.ed(4).String,['Select the location for  ',str]);
% %             str='Background Images';
        case 'pb1_3'
              str='Background Images';
              input_directory=uigetdir(S.ed(5).String,['Select the location for  ',str]);

% %             str='.WAV audio files';
        otherwise
            %do nothing
            str='unexpectederror';
            disp(str)
            return
%             input_directory=uigetdir(cd,['Select the location for  ',str]);
end


if input_directory ~=0  %did we get a folder?


    switch caller
        case 'pb1_1'
            set(S.ed(3),'string',input_directory)
        case 'pb1_2'
            set(S.ed(4),'string',input_directory)
        case 'pb1_3'
            set(S.ed(5),'string',input_directory)
        otherwise
            %do nothing
    end
else
    %do nothing; keep the default paths
end




