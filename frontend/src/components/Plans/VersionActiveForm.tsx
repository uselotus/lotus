import React, { useState } from "react";
import { Button, Divider, Modal, Select, Input, message, Radio } from "antd";

const VersionActiveForm = (props: {
  visible: boolean;
  onCancel: () => void;
  onOk: (active: boolean) => void;
}) => {
  const [active, setActive] = useState<boolean>(false); //id of the target customer

  return (
    <Modal
      visible={props.visible}
      title={"Confirm New Version"}
      okText="Create Version"
      okType="default"
      okButtonProps={{
        type: "primary",
      }}
      onCancel={props.onCancel}
      onOk={() => {
        props.onOk(active);
      }}
    >
      <div className="grid grid-row-3">
        <div className="flex flex-col items-center mb-5">
          <h3>
            * Setting this version to Inactive will publish the version as a
            draft and can be manually converted to active.
          </h3>
          <h3 className="mb-5">
            * Setting this version to active will add all new subscriptions of
            the plan onto this version. You can also choose to migrate existing
            subscriptions.
          </h3>

          <Radio.Group
            onChange={(e) => {
              setActive(e.target.value);
            }}
            buttonStyle="solid"
          >
            <Radio.Button value="false">Inactive</Radio.Button>
            <Radio.Button value="true">Active</Radio.Button>
          </Radio.Group>
        </div>
      </div>
    </Modal>
  );
};

export default VersionActiveForm;
