// @ts-ignore
import React, {FC} from "react";
import "./PlanDetails.css";
import {Component} from "../../../types/plan-type";

interface PlanComponentsProps {
    components?: Component[]
}

const PlanComponents: FC<PlanComponentsProps> = ({components}) => {

    const dummy_components = [
        {
            metric:"API calls",
            cost:"$4 / 20 Unit(s)",
            FreeUnits:10,
            MaxUnits:10,
        },
        {
            metric:"Unique Languages",
            cost:"$4 / 20 Unit(s)",
            FreeUnits:10,
            MaxUnits:10,
        },
        {
            metric:"API calls",
            cost:"$4 / 20 Unit(s)",
            FreeUnits:10,
            MaxUnits:10,
        },
    ]

    return (
        <>
            <div className="px-2 pb-5 pt-3 font-main font-bold font-black">Components:</div>
            <div className="flex items-center justify-start flex-wrap">
                { dummy_components.map( component => (
                    <div className="px-2 py-2 bg-[#FAFAFA] rounded planComponent mr-4 mb-2">
                        <div className="planDetails planComponentMetricName">
                            <div className="pr-1">Metric:</div>
                            <div> {component.metric}</div>
                        </div>
                        <div className="planDetails">
                            <div className="pr-1 planComponentLabel">Cost:</div>
                            <div className="planComponentCost"> {component.cost}</div>
                        </div>
                        <div className="flex items-center">
                            <div className="planDetails pr-6">
                                <div className="pr-2 planComponentLabel">Free Units:</div>
                                <div>{component.FreeUnits}</div>
                            </div>
                            <div className="planDetails">
                                <div className="pr-2 planComponentLabel">Max Units:</div>
                                <div>{component.MaxUnits}</div>
                            </div>
                        </div>
                    </div>
                ))}
            </div>

        </>

    );
};
export default PlanComponents;
