// @ts-ignore
import React, {FC, useState} from "react";
import "./SwitchVersions.css";
import { Button } from "antd";
import { PlusOutlined } from "@ant-design/icons";

interface Version {
    version_name: string
}

interface SwitchVersionProps {
    versions: Version[];
    className: string;
}

const SwitchVersions: FC<SwitchVersionProps> = ({versions, className}) => {
    const [activeVersion, setActiveVersion] = useState(versions[0])

    const isActiveVersion = (version: Version) => activeVersion.version_name === version.version_name;
    return (
        <div className={className}>
            {versions.map(version => (
                <div
                    onClick={() => setActiveVersion(version)}
                    className={[
                        "flex items-center justify-center versionChip mx-1",
                        isActiveVersion(version) ? "bg-[#c3986b] text-white" : "bg-[#EAEAEB] text-black",
                    ].join(" ")}>{version.version_name}
                </div>
            ))}
            <Button type="text">
                <div className="flex items-center justify-center">
                    <div className="addVersionButton" ><PlusOutlined /></div>
                    <div>Add new version</div>
                </div>
            </Button>
        </div>

    );
};
export default SwitchVersions;
