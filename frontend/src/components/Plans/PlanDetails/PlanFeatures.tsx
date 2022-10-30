// @ts-ignore
import React, {FC} from "react";
import "./PlanDetails.css";
import {FeatureType} from "../../../types/feature-type";

interface PlanFeaturesProps {
    features?: FeatureType[]
}

const PlanFeatures: FC<PlanFeaturesProps> = ({features}) => {

    const dummy_features = [
        {
            featureName:"Slack Integration:",
            description:"Lorem ipsum dolor sit amet, consectetur adipiscing elit, sed do eiusmod tempor incididunt ut labore et dolore magna aliqua."
        },
        {
            featureName:"10 Minute SLA:",
            description:"Lorem ipsum dolor sit amet, consectetur adipiscing elit, sed do eiusmod tempor incididunt ut labore et dolore magna aliqua."
        },
    ]

    return (
        <>
            <div className="px-2 pb-5 pt-3 font-main font-bold font-black">Features:</div>
            <div className="flex items-center justify-start flex-wrap">
                { dummy_features.map( feature => (
                    <div className="px-2 py-2 bg-[#FAFAFA] rounded planComponent mr-4 mb-2">
                        <div className="planDetails planComponentMetricName">
                            <div className="pr-1">{feature.featureName}</div>
                        </div>
                        <div className="planFeatureDesc">{feature.description}</div>
                    </div>
                ))}
            </div>

        </>

    );
};
export default PlanFeatures;
