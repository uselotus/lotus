import React, { useState } from "react";
import { Button, Divider, Modal, Select, Input, message, Radio } from "antd";
import { toast } from "react-toastify";

const VersionActiveForm = (props: {
  visible: boolean;
  onCancel: () => void;
  onOk: (active: boolean, activeType: string) => void;
}) => {
  const [active, setActive] = useState<boolean>(false);
  const [activeType, setActiveType] = useState<string>("");

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
        if (active === undefined) {
          toast.error("Please choose whether to activate the new version");
        } else if (active === true && activeType === "") {
          toast.error("Please choose whether to activate the new version");
        } else {
          props.onOk(active, activeType);
        }
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
            <Radio.Button value={false}>Inactive</Radio.Button>
            <Radio.Button value={true}>Active</Radio.Button>
          </Radio.Group>
        </div>
      </div>
      {active === true && (
        <div className="grid grid-row-3 items-center my-5">
          <div className="separator mb-5" />
          <h3 className="mb-5">
            How should subscriptions on the current active version be treated?
          </h3>
          <Select
            onChange={(value) => {
              setActiveType(value);
            }}
          >
            <Select.Option
              value="replace_on_active_version_renewal"
              className="my-3"
            >
              Migrate When Subscriptions Renew
            </Select.Option>
            <Select.Option value="grandfather_active">
              Grandfather Subscriptions, Do Not Migrate
            </Select.Option>
          </Select>
        </div>
      )}
    </Modal>
  );
};

export default VersionActiveForm;
