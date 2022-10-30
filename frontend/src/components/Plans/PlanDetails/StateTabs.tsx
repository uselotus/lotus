// @ts-ignore
import React, {FC, useState} from "react";
import "./StateTabs.css"
import { Tooltip } from 'antd';

interface StateTabsProps {
    tabs?: string[]
    activeTab:string
}

const StateTabs: FC<StateTabsProps> = ({tabs, activeTab}) => {
    const [currentActiveTab , setCurrentActiveTab] = useState(activeTab)

    const getToolTipText = (tab) => {
        switch (tab){
            case "Inactive":
                return "Make this Plan Inactive"
            case "Active":
                return "If you make this version active, your other active version will become inactive."
            case "Grandfathered":
                return "Make this Plan Grandfathered"
        }
    }

    return (
       <div className="flex items-center justify-around tabsContainer">
           {tabs.map(tab => (
               <Tooltip title={getToolTipText(tab)}>
                   <div
                       onClick={() => setCurrentActiveTab(tab)}
                       className={[
                           "tabItem flex items-center",
                           currentActiveTab === tab && "activeTab text-black",
                       ].join(" ")}>
                       {tab}
                   </div>
               </Tooltip>
           ))}
       </div>
    );
};
export default StateTabs;
