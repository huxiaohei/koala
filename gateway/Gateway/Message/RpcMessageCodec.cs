﻿using System;
using System.Buffers;
using System.Collections.Generic;
using System.Linq;
using System.Text;
using System.Text.Json;
using Abstractions.Network;
using DotNetty.Buffers;
using Gateway.NetworkNetty;
using Gateway.Utils;

namespace Gateway.Message
{
    /// <summary>
    /// 4字节magic `KOLA`
    /// 4字节小端Meta Length
    /// 4字节小端Body Length
    /// N字节Meta
    /// M字节Body
    /// </summary>
    public class RpcMessageCodec : IMessageCodec
    {
        readonly int Magic = "KOLA".CastToInt();
        const int HeaderLength = sizeof(int) + sizeof(int) + sizeof(int);
        static Dictionary<string, Type> MessageTypes = new Dictionary<string, Type>();
        readonly byte[] Empty = new byte[0];

        static RpcMessageCodec() 
        {
            var assemblies = AppDomain.CurrentDomain.GetAssemblies();
            foreach (var asm in assemblies.Reverse()) 
            {
                foreach (var t in asm.GetTypes())
                {
                    if (t.IsSubclassOf(typeof(RpcMeta))) 
                    {
                        MessageTypes.Add(t.Name, t);
                    }
                }
            }
        }

        public string CodecName => "RpcMessageCodec";

        public (long length, string typeName, object msg) Decode(IByteBuffer input)
        {
            var readableBytes = input.ReadableBytes;
            if (readableBytes < HeaderLength) 
            {
                return (0, null, null);
            }

            input.MarkReaderIndex();

            var magic = input.ReadIntLE();
            var metaLength = input.ReadIntLE();
            var bodyLength = input.ReadIntLE();
            var totalLength = HeaderLength + metaLength + bodyLength;
            if (readableBytes < totalLength) 
            {
                input.ResetReaderIndex();
                return (0, null, null);
            }
            var nameLength = input.ReadByte();
            var name = input.ReadString(nameLength, Encoding.UTF8);
            if (!MessageTypes.TryGetValue(name, out var messageType)) 
            {
                throw new Exception($"Message:{name} not found");
            }

            var metaBodyLength = metaLength - 1 - name.Length;
            var metaBody = ArrayPool<byte>.Shared.Rent(metaBodyLength);
            try 
            {
                input.ReadBytes(metaBody, 0, metaBodyLength);

                var meta = JsonSerializer.Deserialize(new ReadOnlySpan<byte>(metaBody, 0, metaBodyLength), messageType);
                var body = Empty;
                if (bodyLength > 0)
                {
                    body = new byte[bodyLength];
                    input.ReadBytes(body);
                }
                var msg = new RpcMessage(meta as RpcMeta, body);
                return (totalLength, meta.GetType().Name, msg);
            }
            finally 
            {
                ArrayPool<byte>.Shared.Return(metaBody);
            }
        }

        public object Encode(IByteBufferAllocator allocator, object message)
        {
            var msg = message as RpcMessage;
            var name = StringMap.GetStringBytes(msg.Meta.GetType().Name);
            var meta = JsonSerializer.SerializeToUtf8Bytes(msg.Meta as object);
            var metaLength = 1 + name.Length + meta.Length;
            var bodyLength = msg.Body != null ? msg.Body.Length : 0;
            var totalLength = HeaderLength + metaLength + bodyLength;

            var buffer = allocator.Buffer(totalLength);
            buffer.WriteIntLE(Magic);
            buffer.WriteIntLE(metaLength);
            buffer.WriteIntLE(bodyLength);

            // 1字节NameLength + Name + M字节Meta
            buffer.WriteByte(name.Length);
            buffer.WriteBytes(name);
            buffer.WriteBytes(meta);

            if (msg.Body != null && msg.Body.Length > 0) 
            {
                buffer.WriteBytes(msg.Body);
            }

            return buffer;
        }
    }
}
