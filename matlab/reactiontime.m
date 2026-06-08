function [t] = reactiontime(instants)
%REACTIONTIME measures the time difference between fully hearing the recording
%only gets called by monitorperf.m
% first output column is the reactiontime for recordings, second column
% shows the number of replays for each recording(mostly zeros)
% -9998 Resume
% -9999 Pause
% -1009 Replay
% -1001 Clicks
% -1002 Stops
% -1008 Replay2: Special case when replays are not allowed
%     t=zeros(S.keypresscount,2);  %The first column is the reaction times, the second will be for number of repeats
%     t=zeros(length(instants),2);  %The first column is reaction times, the second will be for number of repeats

if length(find(instants==-1001))~=length(find(instants==-1002))  %checks for equal number of stops and clicks
%     clicks=find(instants==-1001);
    t=0;
    fprintf('unable to calculate reaction time: unequal number of clicks and stops\n')
else
    stops=find(instants==-1002);
    clicks=find(instants==-1001);
    t=zeros(length(clicks),2);
    %     replays=find(instants==-1009);
    %     replays2=find(instants==-1008);
    %     pauses=find(instants==-9999);
    %     resumes=find(instants==-9998);
    
    for i=1:length(clicks) %length(stops)=length(clicks)=S.keypresscount
        if clicks(i)==stops(i)+1  %clicks right after stops, most common scenario
%             t(i,1)=etime(instants(clicks(i),2:7),instants(stops(i),2:7));  %reaction time
            t(i,1)=(instants(clicks(i),2)-instants(stops(i),2))*86400;  %reaction time in seconds
            t(i,2)=0; %zero repeats instants(clicks(i),2:7),instants(stops(i),2:7)
        else
            distance=clicks(i)-stops(i);% an integer greater than 1
            for j=2:distance+1
                nextevent=instants(stops(i)+j-1); %evaluates next events after the stop until reaching the corresponding click
                switch nextevent
                    case -1009 %replays
%                         x1009=[i,j]
                        %                     t(i,1)=etime(instants(stops(i)+j,2:7),instants(stops(i),2:7)); %reaction since the first play
                        %                     t(i,1)=etime(instants(stops(i)+j,2:7),instants(stops(i)+j-1,2:7));
%                         t(i,1)=etime(instants(stops(i)+j-1,2:7),instants(stops(i),2:7))-t(i,1); %reaction since the latest play
                        t(i,1)=(instants(stops(i)+j-1,2)-instants(stops(i),2))*86400-t(i,1); %reaction since the latest play
                        t(i,2)=1+t(i,2);
                    case -1008 % does not ever happen %replays after resuming the test when replay button is deactive
                        %                     t(i,1)=etime(instants(stops(i)+j-1,2:7),instants(stops(i),2:7));
%                         t(i,1)=etime(instants(stops(i)+j-1,2:7),instants(stops(i)+j-2,2:7));
                        t(i,1)=(instants(stops(i)+j-1,2)-instants(stops(i)+j-2,2))*86400;                        
                        %                     t(i,1)=etime(instants(stops(i)+j-1,2:7),instants(stops(i),2:7))-t(i,1);
                        t(i,2)=1.001+t(i,2); %0.001 is sort of a tag to remind of a rare occassion
                    case -9999 %pause (interuption)
                        t(i,2)=1j+t(i,2); %tagging interruptions by adding an imaginary (1j) value to the second column
                    case -9998 %resume
                        %                     t(i,1)=etime(instants(stops(i)+j-1,2:7),instants(stops(i),2:7));
%                         t(i,1)=etime(instants(stops(i)+j-1,2:7),instants(stops(i)+j-2,2:7));
                        t(i,1)=(instants(stops(i)+j-1,2)-instants(stops(i)+j-2,2))*86400;
                        
                        %                     t(i,1)=etime(instants(stops(i)+j-1,2:7),instants(stops(i),2:7))-t(i,1); %if not repeating the last recording right after resuming the task, the reaction time will be calculated since the Resume time, which technically does not have much meaning.
                    case -1001
%                         x1001=[i,j]
                        
                        %                     t(i,1)=etime(instants(stops(i)+j-1,2:7),instants(stops(i),2:7))-t(i,1);
%                         t(i,1)=etime(instants(stops(i)+j-1,2:7),instants(stops(i)+j-2,2:7));
                        t(i,1)=(instants(stops(i)+j-1,2)-instants(stops(i)+j-2,2));                        
                    otherwise
                        %shoud not happen
                        fprintf('unknownerror...reactiontime.m\n')
                end
                
                
                
            end
            
        end
    end
    
    
    
    
end

