import React from "react";
import { Radio } from "antd";

const subscriptionCancellationOptions = [
  { name: "Cancel and Bill  Now", type: "bill_now" },
  { name: "Cancel Renewal", type: "remove_renewal" },
];
const CancelMenuComponent = ({
  setCancelSubType,
}: {
  setCancelSubType: (e: "bill_now" | "remove_renewal") => void;
}) => (
  <div>
    <p className="text-base Inter">
      If you cancel a plan the customer will lose it permanently, and you
      won&apos;t be able to recover it. Do you want to continue?
    </p>
    <Radio.Group
      onChange={(e) => setCancelSubType(e.target.value)}
      buttonStyle="solid"
    >
      <div className="flex flex-row items-center justify-center gap-4">
        {subscriptionCancellationOptions.map((options) => (
          <div
            key={options.type}
            className="flex items-center justify-center gap-2"
          >
            <Radio.Button
              value={options.type}
              defaultChecked={options.type === "bill_now"}
            >
              {options.name}
            </Radio.Button>
          </div>
        ))}
      </div>
    </Radio.Group>
  </div>
);
const CancelMenu = React.memo(CancelMenuComponent);

export default CancelMenu;
