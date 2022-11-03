import { PlusOutlined } from '@ant-design/icons';
import type { InputRef } from 'antd';
import { Input, Tag, Tooltip } from 'antd';
// @ts-ignore
import React, { useEffect, useRef, useState } from 'react';

interface LinkExternalIdsProps {
    externalIds:string[]
}

const LinkExternalIds: React.FC<LinkExternalIdsProps> = ({externalIds}) => {
    const [tags, setTags] = useState<string[]>(externalIds);
    const [inputVisible, setInputVisible] = useState(false);
    const [inputValue, setInputValue] = useState('');
    const inputRef = useRef<InputRef>(null);
    const editInputRef = useRef<InputRef>(null);

    useEffect(() => {
        if (inputVisible) {
            inputRef.current?.focus();
        }
    }, [inputVisible]);

    useEffect(() => {
        editInputRef.current?.focus();
    }, [inputValue]);

    const handleClose = (removedTag: string) => {
        const newTags = tags.filter(tag => tag !== removedTag);
        setTags(newTags);
    };

    const handleInputChange = (e: React.ChangeEvent<HTMLInputElement>) => {
        setInputValue(e.target.value);
    };

    const handleInputConfirm = () => {
        if (inputValue && tags.indexOf(inputValue) === -1) {
            setTags([...tags, inputValue]);
        }
        setInputVisible(false);
        setInputValue('');
    };

    return (
        <>
            {tags.map(tag => {
                const isLongTag = tag.length > 20;
                const tagElem = (
                    <Tag
                        className="edit-tag"
                        key={tag}
                        closable
                        onClose={() => handleClose(tag)}
                    >
            <span>
              {isLongTag ? `${tag.slice(0, 20)}...` : tag}
            </span>
                    </Tag>
                );
                return isLongTag ? (
                    <Tooltip title={tag} key={tag}>
                        {tagElem}
                    </Tooltip>
                ) : (
                    tagElem
                );
            })}
            {inputVisible && (
                <Input
                    ref={inputRef}
                    type="text"
                    size="small"
                    className="tag-input"
                    value={inputValue}
                    onChange={handleInputChange}
                    onBlur={handleInputConfirm}
                    onPressEnter={handleInputConfirm}
                />
            )}
            {!inputVisible && (
                <Tag className="site-tag-plus" onClick={() => setInputVisible(true)}>
                    <PlusOutlined /> Link External Ids
                </Tag>
            )}
        </>
    );
};

export default LinkExternalIds;
