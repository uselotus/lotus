import React, { useState } from "react";
import { FeatureType } from "../../types/feature-type";
import { Button, Divider, Modal, Select, Input } from "antd";
import { features } from "process";

const { Option } = Select;

const FeatureForm = (props: {
  visible: boolean;
  onCancel: () => void;
  features: FeatureType[] | undefined;
  onAddFeatures: (features: FeatureType[]) => void;
}) => {
  const [newFeatures, setNewFeatures] = useState<FeatureType[]>([]);
  const [createdFeatureName, setCreatedFeatureName] = useState<string>("");
  const [createdFeatureDescription, setCreatedFeatureDescription] =
    useState<string>("");

  const addExistingFeatureToList = (feature_add_list: string[]) => {
    if (props.features !== undefined) {
      for (let i = 0; i < feature_add_list.length; i++) {
        setNewFeatures([
          ...newFeatures,
          props.features.find((f) => f.feature_name == feature_add_list[i]),
        ]);
      }
    }
  };

  const addnewFeatureToList = () => {
    if (createdFeatureName !== "") {
      const newFeature: FeatureType = {
        feature_name: createdFeatureName,
        feature_description: createdFeatureDescription,
      };
      setNewFeatures([...newFeatures, newFeature]);
      setCreatedFeatureName("");
      setCreatedFeatureDescription("");
    }
  };
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
            onChange={addExistingFeatureToList}
            value={newFeatures.map((f) => f.feature_name)}
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
        <div className="flex flex-col space-y-3">
          <h3>Add A New Feature</h3>
          <Input
            placeholder={"Feature Name"}
            value={createdFeatureName}
            onChange={(e) => setCreatedFeatureName(e.target.value)}
          ></Input>
          <Input
            placeholder={"Feature Description"}
            value={createdFeatureDescription}
            onChange={(e) => setCreatedFeatureDescription(e.target.value)}
          ></Input>

          <Button onClick={addnewFeatureToList}>Add Feature</Button>
        </div>
      </div>
    </Modal>
  );
};

export default FeatureForm;
