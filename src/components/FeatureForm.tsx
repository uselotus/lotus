import { FC, useState } from "react";
import { FeatureType } from "../types/feature-type";
import { Divider, Modal, Select } from "antd";

const { Option } = Select;

const FeatureForm = (props: {
  visible: boolean;
  onCancel: () => void;
  features: FeatureType[] | undefined;
  onAddFeatures: (features: string[]) => void;
}) => {
  const [newFeatures, setNewFeatures] = useState<string[]>([]);

  return (
    <Modal
      visible={props.visible}
      title={"Add Features"}
      okText="Add"
      okType="default"
      cancelText="Cancel"
      onCancel={props.onCancel}
      onOk={() => {
        props.onAddFeatures(newFeatures);
      }}
    >
      <div className="grid grid-row-3">
        <div className="flex flex-col">
          <Select
            showSearch
            mode="multiple"
            placeholder="Select A Feature"
            optionFilterProp="children"
            onChange={setNewFeatures}
            filterOption={(input, option) =>
              (option!.children as unknown as string)
                .toLowerCase()
                .includes(input.toLowerCase())
            }
          >
            {props.features?.map((feat) => (
              <Option value={feat.feature_name}>{feat.feature_name}</Option>
            ))}
          </Select>
        </div>
        <Divider />
        <div className="flex flex-col">
          <h3>Add A New Feature</h3>
        </div>
      </div>
    </Modal>
  );
};

export default FeatureForm;
